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

import json

import aiohttp
import gidgethub.aiohttp

from aiohttp import web

from browntruck.utils import get_install_token


async def integration_installation_hook(request):
    payload = await request.read()

    data = json.loads(payload.decode(request.charset or "utf8"))
    installation_token = await get_install_token(
	app_id=app["github_app_id"],
	private_key=app["github_app_private_key"],
	install_id=data["installation"]["id"],
	payload=data,
    )

    async with aiohttp.ClientSession() as session:
        gh = gidgethub.aiohttp.GitHubAPI(
            session,
            "BrownTruck-Bot"  # TODO: add "/1.0" as in version
            " (+https://github.com/pypa/browntruck)",
            oauth_token=request.app["github_token"],
        )
	# ...

    return web.json_response({
	"message": "installation recorded",
    })
