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

import aiohttp

import gidgethub
import gidgethub.aiohttp


async def check_prs(app):
    async with aiohttp.ClientSession() as session:
        gh = gidgethub.aiohttp.GitHubAPI(
            session,
            "BrownTruck",
            oauth_token=app["github_token"],
        )

        async for pr in gh.getiter(f"/repos/{app['repo']}/pulls?sort=updated"):
            # Determine if our PR is mergeable or not.
            tries = 5
            while True:
                try:
                    pr_data = await gh.getitem(pr["url"])
                except gidgethub.BadRequest as exc:
                    if (isinstance(exc.status_code, http.HTTPStatus.NOT_FOUND)
                            and tries > 0):
                        tries -= 1
                        await asyncio.sleep(1)
                    raise
                else:
                    pr = pr_data
                    break
            mergeable = pr["mergeable"]

            # If there isn't a mergeable state for this PR at all, then we will
            # just skip processing it. Hopefully on the next pass it will have
            # one and we can process it then.
            if mergeable is None:
                continue

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

            if mergeable and "needs merged or rebased" in labels:
                # The PR is now mergeable and no longer requires a merge or a
                # rebase, so we'll go ahead and remove the label.
                await gh.delete(issue_data["labels_url"],
                                {"name": "needs merged or rebased"})
            elif not mergeable and "needs merged or rebased" not in labels:
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
                              data=["needs merged or rebased"])
