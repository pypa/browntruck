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
from browntruck.commands.request_review import RequestReviewCommand
from browntruck.hooks.commands import CommandWebhook
from browntruck.hooks.logger import LoggerWebhook
from browntruck.hooks.merge_conflict import MergeConflictWebhook
from browntruck.hooks.news import NewsFileWebhook


config = Configuration(
    oauth_token=os.environ.pop("GITHUB_TOKEN"),
    gh_username=os.environ.pop("GITHUB_USERNAME"),
)


hook_logger = LoggerWebhook()
hook_commands = CommandWebhook(config=config)
hook_merge_conflict = MergeConflictWebhook(config=config)
hook_news = NewsFileWebhook(config=config)

command_request_review = RequestReviewCommand()
