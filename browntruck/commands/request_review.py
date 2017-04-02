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

import attr
import gidgethub.sansio


from twisted.logger import Logger
from twisted.internet import defer
from twisted.plugin import IPlugin
from zope.interface import implementer

from ..hooks.commands import ICommand
from ..utils import getGitHubAPI, getGHItem, retry


log = Logger()


@implementer(IPlugin, ICommand)
@attr.s
class RequestReviewCommand:

    config = attr.ib()
    command_regex = r"^request\s+review$"

    def run(self, commentData, requestID):
        return defer.ensureDeferred(self.hook(commentData))

    async def hook(self, commentData, requestID):
        log.info("Processing review request for {commentData[url]}",
                 commentData=commentData)

        gh = getGitHubAPI(oauth_token=self.config.oauth_token)

        # Grab the issue data from GitHub
        issueData = await getGHItem(gh, commentData["issue_url"], requestID)

        # Check to see if this comment is even on an issue, if it's not then
        # we can just bail out now.
        if not issueData.get("pull_request"):
            log.info("{commentData[url]} is not a pull request.",
                     commentData=commentData)
            return

        # Grab the PR data from Github.
        prData = await getGHItem(gh,
                                 issueData["pull_request"]["url"], requestID)

        # Grab the list of reviews on this PR
        # TODO: When this API is no longer in beta, stop doing this manually.
        async for attempt in retry():
            with attempt:
                reviews = []
                for review in gh.getiter(prData["url"] + "/reviews",
                                         accept=gidgethub.sansio.accept_format(
                                            version="black-cat-preview")):
                    reviews.append(review)

        # Actually go through and dismiss all of our pending reviews.
        # TODO: When this API is no longer in beta, stop doing this manually.
        for review in reviews:
            async for attempt in retry():
                with attempt:
                    gh.put(prData["url"] + "/reviews{/review_id}/dismissals",
                           {"review_id": review["id"]},
                           accept=gidgethub.sansio.accept_format(
                                version="black-cat-preview"))

        log.info("Review requested for {commentData[url]}",
                 commentData=commentData)
