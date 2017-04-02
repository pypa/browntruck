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

import collections
import re

import attr

from txghbot import IWebhook
from twisted.logger import Logger
from twisted.internet import defer
from twisted.plugin import IPlugin, getPlugins
from zope.interface import Attribute, Interface, implementer

from ..utils import getGitHubAPI, getGHItem


ACTIONS = {"created", "edited"}


log = Logger()


class ICommand(Interface):

    command_regex = Attribute("""
        A string that contains a regex to match an incoming command against.
    """)

    def run(self, commentData):
        """ Run this command on the object specified by commentData. """


@implementer(IPlugin, IWebhook)
@attr.s
class CommandWebhook:

    config = attr.ib()

    @property
    def commands(self):
        if not hasattr(self, "_commands"):
            self._commands = collections.OrderedDict(
                (re.compile(p.command_regex), p) for p in getPlugins(ICommand))

        return self._commands

    def match(self, eventName, eventData):
        return (eventName == "issue_comment"
                and eventData.get("action") in ACTIONS)

    def run(self, eventName, eventData, requestID):
        return defer.ensureDeferred(self.hook(eventName, eventData, requestID))

    async def hook(self, eventName, eventData, requestID):
        log.info("Processing {eventData[number]}", eventData=eventData)

        gh = getGitHubAPI(oauth_token=self.config.oauth_token)

        # Fetch all of the related data from GitHub, we do this instead of
        # trusting the event data from the hook to help both with stale hooks
        # as well as better security.
        commentData = await getGHItem(gh,
                                      eventData["comment"]["url"], requestID)

        # Now parse the comment data looking for commands. The basic rules of
        # this that commands must each be on their own line and they are case
        # sensitive.
        dls = []
        for line in commentData["body"].splitlines():
            line = line.strip()

            # All of our commands have to be addressed to the bot, this serves
            # as a sort of watch word to avoid mistaken commands.
            if (not line.lower().startswith(
                                    "@" + self.config.gh_username.lower())):
                continue
            else:
                # We want to get rid of the bot name from out line, as well as
                # restrip any left over whitespace.
                line = line[len(self.config.gh_username) + 1].strip()

            # Take our line, and see if it matches any commands, if so run it
            # and add it to our list of deferreds to wait until the end.
            for command_regex, command in self.commands.items():
                if command_regex.search(line.strip()):
                    dls.append(defer.maybeDeferred(command.run(commentData)))
                    break

        await defer.gatherResults(dls, consumeErrors=True)
