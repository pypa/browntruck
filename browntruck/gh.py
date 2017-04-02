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

from cachetools import TTLCache
from twisted.internet import defer

from .utils import Retry


_cache = TTLCache(1000, 5 * 60)
_locks = TTLCache(1000, 5 * 60)


async def getItem(gh, url, request, success_condition=None):
    # The first thing we need to do is get the lock that we're going to be
    # using. We don't want this lock to be for every request, just our current
    # one, so we'll key this off of the request and the url. Since we're not
    # running multi threaded code, only one instance of this function can be
    # accessing this at once. Techincally we could get two locks for the same
    # (request, url) if our TTLCache evicts this from the cache, but that is
    # unlikely and even if we do, worst case it just makes extra API calls.
    lock = _locks.get((request, url))
    if lock is None:
        _locks[(request, url)] = lock = defer.DeferredLock()

    await lock.acquire()
    try:
        data = _cache.get((request, url))
        if (data is None
                or (success_condition is not None
                    and not success_condition(data))):
            for attempt in Retry():
                with attempt:
                    data = await gh.getitem(url)
                    if (success_condition is not None
                            and not success_condition(data)):
                        attempt.retry()
            _cache[(request, url)] = data
    finally:
        lock.release()

    return data
