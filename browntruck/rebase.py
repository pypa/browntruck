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
import json

import aiohttp
import gidgethub
import gidgethub.aiohttp

from aiohttp import web

from browntruck.utils import verify_signature, InvalidSignature


async def _check_pr(gh, pr_url):
    print(f"Checking mergeable status for: {pr_url!r}")

    # Determine if our PR is mergeable or not.
    tries = 5
    while True:
        try:
            pr_data = await gh.getitem(pr_url)
        except gidgethub.BadRequest as exc:
            if (isinstance(exc.status_code, http.HTTPStatus.NOT_FOUND)
                    and tries > 0):
                tries -= 1
                await asyncio.sleep(1)
            raise
        else:
            pr = pr_data
            mergeable = pr["mergeable"]
            if mergeable is not None:
                break
            else:
                tries -= 1
                await asyncio.sleep(1)

    # Grab our labels out of GitHub's API
    tries = 5
    while True:
        try:
            issue_data = await gh.getitem(pr["issue_url"])
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

    if mergeable and "needs rebase or merge" in labels:
        # The PR is now mergeable and no longer requires a merge or a
        # rebase, so we'll go ahead and remove the label.
        await gh.delete(issue_data["labels_url"],
                        {"name": "needs rebase or merge"})
    elif not mergeable and "needs rebase or merge" not in labels:
        # The PR is not mergeable, so we'll mark it and add our comment
        # to it explaining what needs to be done.
        comment = (
            "Hello!\n\n"
            "I am an automated bot and I have noticed that this pull "
            "request is not currently able to be merged. If you are "
            "able to either merge the ``master`` branch into this "
            "pull request or rebase this pull request against "
            "``master`` then it will eligible for code review and "
            "hopefully merging!"
        )
        await gh.post(issue_data["comments_url"], data={
            "body": comment,
        })
        await gh.post(issue_data["labels_url"],
                      data=["needs rebase or merge"])


async def check_prs(app):
    async with aiohttp.ClientSession() as session, app["redis.pool"].get() as redis:
        gh = gidgethub.aiohttp.GitHubAPI(
            session,
            "BrownTruck",
            oauth_token=app["github_token"],
        )

        async for pr in gh.getiter(f"/repos/{app['repo']}/pulls?sort=updated"):
            rkey = f"rebase/{pr['number']}"
            if not (await redis.exists(rkey)):
                await _check_pr(gh, pr["url"])
                await redis.setex(rkey, 1 * 24 * 60 * 60, "")
            else:
                print(f"Skipping {pr['url']!r}. It has already been checked today.")


async def needs_rebase_hook(request):
    payload = await request.read()

    # Verify the payload against the signature
    if (request.headers.get("X-Hub-Signature")
            and request.app.get("github_payload_key")):
        try:
            verify_signature(
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
    if (data.get("action") not in {"opened", "reopened", "synchronize"}):
        return web.json_response({"message": "Skipped due to action"})

    # Check our PR
    async with aiohttp.ClientSession() as session:
        gh = gidgethub.aiohttp.GitHubAPI(
            session,
            "BrownTruck",
            oauth_token=request.app["github_token"],
        )
        await _check_pr(gh, data["pull_request"]["url"])

    return web.Response(status=204)
