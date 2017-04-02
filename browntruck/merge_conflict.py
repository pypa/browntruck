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


from txghbot import IWebhook
from twisted.internet import defer
from twisted.logger import Logger
from twisted.plugin import IPlugin
from zope.interface import implementer

from .utils import getGitHubAPI, Retry


ACTIONS = {"opened", "reopened", "synchronize"}

MESSAGE = """
Hello!

I am an automated bot and I have noticed that this pull request is not \
currently able to be merged. If you are able to either merge the ``master`` \
branch into this pull request or rebase this pull request against ``master`` \
then it will eligible for code review and hopefully merging!
""".strip()


log = Logger()


@implementer(IPlugin, IWebhook)
@attr.s
class MergeConflictWebhook:

    config = attr.ib()

    def match(self, eventName, eventData):
        return (eventName == "pull_request"
                and eventData.get("action") in ACTIONS)

    def run(self, eventName, eventData, requestID):
        return defer.ensureDeferred(self.hook(eventName, eventData, requestID))

    async def hook(self, eventName, eventData, requestID):
        log.info("Processing {eventData[number]}", eventData=eventData)

        gh = getGitHubAPI(oauth_token=self.config.oauth_token)

        # First things first, we want to fetch the whole PR data from GitHub
        # instead of relying on what was sent in the Hook. This will ensure
        # that we have the latest data as well as be more secure. We will also
        # continue to attempt to fetch the data until the mergeable attribute
        # has a value.
        for attempt in Retry():
            with attempt:
                prData = await gh.getitem(eventData["pull_request"]["url"])
                if prData["mergeable"] is None:
                    attempt.retry()

        # Next, we want to fetch the issue data, we need this seperately from
        # the PR data because not everything is contained within the PR since
        # GitHub models PRs as issues with attached code.
        for attempt in Retry():
            with attempt:
                issueData = await gh.getitem(prData["issue_url"])

        # We also need our label data since a PR can be marked as trivial which
        # skips the requirement for a news file.
        for attempt in Retry():
            with attempt:
                labelData = await gh.getitem(issueData["labels_url"])
        labels = {l["name"] for l in labelData}

        # Actually determine if our PR is mergeable, and if so properly add
        # the labels and comments that we require.
        if prData["mergeable"] and "needs merged or rebased" in labels:
            # The PR is now mergeable and no longer requires a merge or a
            # rebase, so we'll go ahead and remove the label.
            await gh.delete(issueData["labels_url"],
                            {"name": "needs merged or rebased"})

            log.info("{prData[number]}: {status}",
                     prData=prData,
                     status="Free of merge conflicts")
        elif (not prData["mergeable"]
                and "needs merged or rebased" not in labels):
            # The PR is not mergeable, so we'll mark it and add our comment
            # to it explaining what needs to be done.
            await gh.post(issueData["comments_url"], data={"body": MESSAGE})
            await gh.post(issueData["labels_url"],
                          data=["needs merged or rebased"])

            log.info("{prData[number]}: {status}",
                     prData=prData,
                     status="Merge conflict detected")
