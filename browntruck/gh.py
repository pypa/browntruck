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

import weakref

from twisted.internet import defer

from .utils import Retry

_NOTHING = object()


_cache = weakref.WeakKeyDictionary()
_locks = weakref.WeakKeyDictionary()


def _get_cache_and_lock(url, request):
    # We use a per release ID cache and set of locks.
    request_cache = _cache.get(request, _NOTHING)
    request_lock = _locks.get(request, _NOTHING)
    if request_cache is _NOTHING:
        _cache[request] = request_cache = weakref.WeakKeyDictionary()
    if request_lock is _NOTHING:
        _locks[request] = request_lock = weakref.WeakKeyDictionary()

    # We need a lock specific to this URL now.
    url_lock = request_lock.get(url, _NOTHING)
    if url_lock is _NOTHING:
        request_lock[url] = url_lock = defer.DeferredLock()

    return request_cache, url_lock


async def getItem(gh, url, request, success_condition=None):
    request_cache, url_lock = _get_cache_and_lock(url, request)

    await url_lock.acquire()
    try:
        data = request_cache.get(url, _NOTHING)
        if (data is _NOTHING
                or (success_condition is not None
                    and not success_condition(data))):
            for attempt in Retry():
                with attempt:
                    data = await gh.getitem(url)
                    if (success_condition is not None
                            and not success_condition(data)):
                        attempt.retry()
            request_cache[url] = data
    finally:
        url_lock.release()

    return data
