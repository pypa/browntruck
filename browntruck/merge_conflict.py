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

from .utils import getGitHubAPI, getGHItem


ACTIONS = {"opened", "reopened", "synchronize"}

LABEL = "needs rebase or merge"

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

        # Fetch all of the related data from GitHub, we do this instead of
        # trusting the event data from the hook to help both with stale hooks
        # as well as better security.
        prData = await getGHItem(gh,
                                 eventData["pull_request"]["url"], requestID,
                                 success_condition=lambda d: (
                                    d["mergeable"] is not None))
        issueData = await getGHItem(gh, prData["issue_url"], requestID)
        labelData = await getGHItem(gh, issueData["labels_url"], requestID)

        # We really only care about just a list of label names.
        labels = {l["name"] for l in labelData}

        # Actually determine if our PR is mergeable, and if so properly add
        # the labels and comments that we require.
        if prData["mergeable"] and LABEL in labels:
            # The PR is now mergeable and no longer requires a merge or a
            # rebase, so we'll go ahead and remove the label.
            await gh.delete(issueData["labels_url"], {"name": LABEL})

            log.info("{prData[number]}: {status}",
                     prData=prData,
                     status="Free of merge conflicts")
        elif not prData["mergeable"] and LABEL not in labels:
            # The PR is not mergeable, so we'll mark it and add our comment
            # to it explaining what needs to be done.
            await gh.post(issueData["comments_url"], data={"body": MESSAGE})
            await gh.post(issueData["labels_url"], data=[LABEL])

            log.info("{prData[number]}: {status}",
                     prData=prData,
                     status="Merge conflict detected")
