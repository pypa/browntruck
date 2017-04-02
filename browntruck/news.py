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

import io
import re

import attr
import treq
import unidiff

from txghbot import IWebhook
from twisted.internet import defer
from twisted.logger import Logger
from twisted.plugin import IPlugin
from zope.interface import implementer

from .utils import getGitHubAPI, Retry


NEWS_FILE_CONTEXT = "news-file/pr"

HELP_URL = "https://pip.pypa.io/en/latest/development/#adding-a-news-entry"

ACTIONS = {"labeled", "unlabeled", "opened", "reopened", "synchronize"}


log = Logger()


_news_fragment_re = re.compile(
    r"news/[^\./]+\.(removal|feature|bugfix|doc|vendor|trivial)$"
)


@implementer(IPlugin, IWebhook)
@attr.s
class NewsFileWebhook:

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
        # that we have the latest data as well as be more secure.
        for attempt in Retry():
            with attempt:
                prData = await gh.getitem(eventData["pull_request"]["url"])

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

        # Finally, we need to fetch the diff from GitHub so that we can see if
        # the user has added any news fragments to our news directory.
        diff = unidiff.PatchSet(io.StringIO(
            await treq.text_content(await treq.get(prData["diff_url"]))))

        # Determine if the status check for this PR is passing or not and
        # update the status check to account for that.
        if ("trivial" in labels
                or any(f.is_added_file for f in diff
                       if _news_fragment_re.search(f.path))):
            await gh.post(
                prData["statuses_url"],
                data={
                    "context": NEWS_FILE_CONTEXT,
                    "target_url": HELP_URL,
                    "state": "success",
                    "description":
                        "News files updated and/or change is trivial.",
                },
            )

            log.info("{prData[number]}: {status}",
                     prData=prData,
                     status="news file updated and/or ignored")
        else:
            await gh.post(
                prData["statuses_url"],
                data={
                    "context": NEWS_FILE_CONTEXT,
                    "target_url": HELP_URL,
                    "state": "failure",
                    "description":
                        "Missing either a news entry or a trivial file/label.",
                },
            )

            log.info("{prData[number]}: {status}",
                     prData=prData,
                     status="news file was not updated",
                     labels=labels,
                     files=[
                        {"path": f.path, "is_added_file": f.is_added_file}
                        for f in diff
                     ])
