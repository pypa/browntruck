# Licensed under the Apache License, Version 2.0 (the "License");
# you may not use this file except in compliance with the License.
# You may obtain a copy of the License at
#
# http://www.apache.org/licenses/LICENSE-2.0
#
# Unless required by applicable law or agreed to in writing, software
# distributed under the License is distributed on an "AS IS" BASIS,
# WITHOUT WARRANTIES OR CONDITIONS OF ANY KIND, either express or implied.
# See the License for the specific language governing permissions and
# limitations under the License.

import asyncio
import http
import io
import json
import re

import aiohttp
import gidgethub
import gidgethub.aiohttp
import gidgethub.sansio
import unidiff

from aiohttp import web


_news_fragment_re = re.compile(
    r"news/[^\./]+\.(removal|feature|bugfix|doc|vendor|trivial)$"
)


NEWS_FILE_CONTEXT = "news-file/pr"

HELP_URL = "https://pip.pypa.io/en/latest/development/#adding-a-news-entry"


async def news_hook(request):
    payload = await request.read()
    try:
        event = gidgethub.sansio.Event.from_http(request.headers, payload,
                                                 secret=request.app.get("github_payload_key"))
    except gidgethub.ValidationFailure:
            return web.json_response(
                {"message": "Invalid signature"},
                status=400,
            )

    data = event.data

    # We only care about a few different kinds of actions, the rest of them
    # are not useful to us, so we'll no-op out quickly if it is one of them.
    if (data.get("action")
            not in {"labeled", "unlabeled", "opened", "reopened",
                    "synchronize"}):
        return web.json_response({"message": "Skipped due to action"})

    async with aiohttp.ClientSession() as session:
        gh = gidgethub.aiohttp.GitHubAPI(
            session,
            "BrownTruck",
            oauth_token=request.app["github_token"],
        )

        # Grab our labels out of GitHub's API
        tries = 5
        while True:
            try:
                issue_data = await gh.getitem(data["pull_request"]["issue_url"])
                label_data = await gh.getitem(issue_data["labels_url"])
            except gidgethub.BadRequest as exc:
                if (isinstance(exc.status_code, http.HTTPStatus.NOT_FOUND)
                        and tries > 0):
                    tries -= 1
                    await asyncio.sleep(1)
                raise
            else:
                break

        labels = {l["name"] for l in label_data}

        # Grab the diff from GitHub and parse it into a diff object.
        diff_url = data["pull_request"]["diff_url"]
        async with session.get(diff_url) as resp:
            diff = unidiff.PatchSet(io.StringIO(await resp.text()))

        # Determine if the status check for this PR is passing or not and
        # update the status check to account for that.
        if ("trivial" in labels
                or any(f.is_added_file for f in diff
                       if _news_fragment_re.search(f.path))):
            await gh.post(
                data["pull_request"]["statuses_url"],
                data={
                    "context": NEWS_FILE_CONTEXT,
                    "target_url": HELP_URL,
                    "state": "success",
                    "description":
                        "News files updated and/or change is trivial.",
                },
            )

            return web.json_response({
                "message": "news file updated and/or ignored",
            })
        else:
            await gh.post(
                data["pull_request"]["statuses_url"],
                data={
                    "context": NEWS_FILE_CONTEXT,
                    "target_url": HELP_URL,
                    "state": "failure",
                    "description":
                        "Missing either a news entry or a trivial file/label.",
                },
            )

            return web.json_response({
                "message": "news file was not updated",
                "labels": list(labels),
                "files": [
                    {"path": f.path, "is_added_file": f.is_added_file}
                    for f in diff
                ],
            })
