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

import hmac
import time

import jwt

class InvalidSignature(Exception):
    pass


def verify_signature(key, signature, body):
    digest = hmac.new(key.encode("ascii"), msg=body, digestmod="sha1")
    if not hmac.compare_digest(f"sha1={digest.hexdigest().lower()}",
                               signature.lower()):
        raise InvalidSignature


def get_gh_jwt(app_id, private_key):
    """Create a signed JWT, valid for 60 seconds."""
    now = int(time.time())
    payload = {
        "iat": now,
        "exp": now + 60,
        "iss": app_id
    }
    return jwt.encode(
        payload,
        key=private_key,
        algorithm="RS256"
    ).decode('utf-8')
