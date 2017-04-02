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

from txghbot import IWebhook
from twisted.internet import defer
from twisted.plugin import IPlugin
from zope.interface import implementer

from .utils import getGitHubAPI


ACTIONS = {"labeled", "unlabeled", "opened", "reopened", "synchronize"}


@implementer(IPlugin, IWebhook)
class NewsFileWebhook(object):

    def match(self, eventName, eventData):
        return (eventName == "pull_request"
                and eventData.get("action") in ACTIONS)

    @defer.ensureDeferred
    def run(self, eventName, eventData, requestID):
        gh = getGitHubAPI()
