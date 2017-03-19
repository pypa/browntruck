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
import json
import re

import aiohttp
import unidiff

from aiohttp import web


_news_fragment_re = re.compile(
    r"news/[^\.]+\.(removal|feature|bugfix|doc|vendor|trivial)]"
)


async def news_hook(request):
    payload = await request.read()

    # Verify the payload against the signature
    # TODO :verify

    data = json.loads(payload.decode(request.charset or "utf8"))

    # We only care about a few different kinds of actions, the rest of them
    # are not useful to us, so we'll no-op out quickly if it is one of them.
    if (data.get("action")
            not in {"labeled", "unlabeled", "opened", "reopened"}):
        return web.json_response({"message": "Skipped due to action"})

    async with aiohttp.ClientSession() as session:
        # Grab our labels out of GitHub's API
        issue_url = data["pull_request"]["issue_url"]
        label_url = f"{issue_url}/labels"
        async with session.get(label_url) as resp:
            label_data = await resp.json()
        labels = {l["name"] for l in label_data}

        # Grab the diff from GitHub and parse it into a diff object.
        diff_url = data["pull_request"]["diff_url"]
        async with session.get(diff_url) as resp:
            diff = unidiff.PatchSet(await resp.text())

    # Determine if the status check for this PR is passing or not and update the
    # status check to account for that.
    if ("trivial" in labels
            or any(f.is_added_file for f in diff
                   if _news_fragment_re.search(f.path))):
        # TODO: Update the status check.

        return web.json_response({
            "message": "news file updated and/or ignored",
        })
    else:
        return web.json_response({
            "message": "news file was not updated",
            "labels": list(labels),
            "files": [
                {"path": f.path, "is_added_file": f.is_added_file}
                for f in diff
            ],
        })


def create_app(*, loop=None):
    app = web.Application(loop=loop)
    app.router.add_post("/hooks/news", news_hook)

    return app


def main(argv):
    loop = asyncio.get_event_loop()
    app = create_app(loop=loop)

    return app
