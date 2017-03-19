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
import hmac
import io
import json
import os
import re

import aiohttp
import gidgethub.aiohttp
import unidiff

from aiohttp import web


_news_fragment_re = re.compile(
    r"news/[^\./]+\.(removal|feature|bugfix|doc|vendor|trivial)$"
)


NEWS_FILE_CONTEXT = "news-file/pr"


class InvalidSignature(Exception):
    pass


def _verify_signature(key, signature, body):
    digest = hmac.new(key, msg=body, digestmod="sha1").hexdigest().lower()
    signature = f"sha1={digest}"

    if not hmac.compare_digest(f"sha1={digest}", signature.lower()):
        raise InvalidSignature


async def news_hook(request):
    payload = await request.read()

    # Verify the payload against the signature
    if (request.headers.get("X-Hub-Signature")
            and request.app.get("github_payload_key")):
        try:
            _verify_signature(
                request.app["github_payload_key"],
                request.headers["X-Hub-Signature"],
                payload,
            )
        except InvalidSignature:
            return web.json_response(
                {"message": "Invalid signature"},
                status=400,
            )

    data = json.loads(payload.decode(request.charset or "utf8"))

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
        issue_data = await gh.getitem(data["pull_request"]["issue_url"])
        label_data = await gh.getitem(issue_data["labels_url"])
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


def create_app(*, github_token, github_payload_key, loop=None):
    app = web.Application(loop=loop)
    app["github_token"] = github_token
    app["github_payload_key"] = github_payload_key
    app.router.add_post("/hooks/news", news_hook)

    return app


def main(argv):
    loop = asyncio.get_event_loop()
    app = create_app(
        github_token=os.environ.get("GITHUB_TOKEN"),
        github_payload_key=os.environ.get("GITHUB_PAYLOAD_KEY"),
        loop=loop,
    )

    return app
