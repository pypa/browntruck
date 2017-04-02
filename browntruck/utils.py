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

from gidgethub.treq import GitHubAPI


def getGitHubAPI(*, oauth_token=None):
    return GitHubAPI("BrownTruck", oauth_token=oauth_token)


@attr.s
class Attempt:

    number = attr.ib()
    retried = attr.ib()
    catch = attr.ib()
    successful = attr.ib(default=None, init=False)

    def __enter__(self):
        return self

    def __exit__(self, exc_type, exc_value, traceback):
        # Our call was successful, so we can mark ourselves as successful.
        if exc_type is None:
            self.successful = True
        # If our current attempt is less than our total number of retries, then
        # we want to suppress the exception, our outer loop will ensure that
        # we get called again.
        elif issubclass(exc_type, self.catch) and self.number < self.retries:
            return True


@attr.s
class Retry:

    catch = attr.ib(default=(Exception,))
    retries = attr.ib(default=5)

    def __iter__(self):
        # We want to effectively run forever until our latest attempt tells us
        # to stop. When we reach our maximum number of retries our Attempt
        # class will let the exception propagate instead of silencing it, so
        # that will break us out of the loop.
        number, attempt = 0, None
        while attempt is None or not attempt.successful:
            number += 1
            attempt = Attempt(number=number, retries=self.retries,
                              catch=tuple(self.catch))
            yield attempt
