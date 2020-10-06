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
import os

from browntruck.config import Configuration
from browntruck.hooks.commands import CommandWebhook
from browntruck.hooks.logger import LoggerWebhook
from browntruck.hooks.merge_conflict import MergeConflictWebhook
from browntruck.hooks.news import NewsFileWebhook

from twisted.web import server
from twisted.application import service, strports, internet

import txghbot


config = Configuration(
    oauth_token=os.environ.pop("GITHUB_TOKEN"),
    port=os.environ.pop("PORT"),
    gh_username=os.environ.pop("GITHUB_USERNAME"),
    gh_payload_key=os.environ.pop("GITHUB_PAYLOAD_KEY"),
)

hooks = [
    LoggerWebhook(),
    CommandWebhook(config=config),
    MergeConflictWebhook(config=config),
    NewsFileWebhook(config=config),
]


application = service.Application("Brown Truck")

site = server.Site(
    txghbot.makeWebhookDispatchingResource(
        config.gh_payload_key,
        hooks,
    ),
)
web_service = strports.service("tcp:" + config.port, site)
web_service.setServiceParent(application)

timer_service = internet.TimerService(1.0, print, "tick")
timer_service.setServiceParent(application)
