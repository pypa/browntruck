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

from cachetools import TTLCache
from gidgethub.treq import GitHubAPI
from twisted.internet import defer, task, reactor


def getGitHubAPI(*, oauth_token=None):
    return GitHubAPI("BrownTruck", oauth_token=oauth_token)


async def getGHItem(gh, url, request, success_condition=None):
    # The first thing we need to do is get the lock that we're going to be
    # using. We don't want this lock to be for every request, just our current
    # one, so we'll key this off of the request and the url. Since we're not
    # running multi threaded code, only one instance of this function can be
    # accessing this at once. Techincally we could get two locks for the same
    # (request, url) if our TTLCache evicts this from the cache, but that is
    # unlikely and even if we do, worst case it just makes extra API calls.
    lock = getGHItem.locks.get((request, url))
    if lock is None:
        getGHItem.locks[(request, url)] = lock = defer.DeferredLock()

    await lock.acquire()
    try:
        data = getGHItem.cache.get((request, url))
        if (data is None
                or (success_condition is not None
                    and not success_condition(data))):
            async for attempt in retry():
                with attempt:
                    data = await gh.getitem(url)
                    if (success_condition is not None
                            and not success_condition(data)):
                        attempt.retry()
            getGHItem.cache[(request, url)] = data
    finally:
        lock.release()

    return data


getGHItem.cache = TTLCache(1000, 5 * 60)
getGHItem.locks = TTLCache(1000, 5 * 60)


class ForceRetry(BaseException):
    pass


@attr.s
class Attempt:

    number = attr.ib()
    retries = attr.ib()
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
        elif (issubclass(exc_type, self.catch + (ForceRetry,))
                and self.number < self.retries):
            return True

    def retry(self):
        raise ForceRetry


async def retry(*, catch=(Exception,), retries=5):
    # We want to effectively run forever until our latest attempt tells us to
    # stop. When we reach our maximum number of retries our Attempt class will
    # let the exception propagate instead of silencing it, so that will break
    # us out of the loop.
    number, attempt, first = 0, None, True
    while attempt is None or not attempt.successful:
        if first:
            first = False
        else:
            await task.deferLater(reactor, 1, lambda: None)

        number += 1
        attempt = Attempt(number=number, retries=retries, catch=tuple(catch))
        yield attempt
