import aiohttp
import random
import json
import time
import asyncio
from typing import Dict, Any, Optional, Tuple
from kirara_ai.logger import get_logger

logger = get_logger("ImageGenerator")

class WebImageGenerator:
    MODELSCOPE_MODELS = {
        "flux": {
            "path": "ByteDance/Hyper-FLUX-8Steps-LoRA",
            "fn_index": 0,
            "trigger_id": 18,
            "data_builder": lambda height, width, prompt: [height, width, 8, 3.5, prompt, random.randint(0, 9999999999999999)],
            "data_types": ["slider", "slider", "slider", "slider", "textbox", "number"],
            "url_processor": lambda url: url.replace("leofen/flux_dev_gradio", "muse/flux_dev"),
            "output_parser": lambda data: data["output"]["data"][0]["url"]
        },
        "ketu": {
            "path": "AI-ModelScope/Kolors",
            "fn_index": 0,
            "trigger_id": 23,
            "data_builder": lambda height, width, prompt: [prompt, "", height, width, 20, 5, 1, True, random.randint(0, 9999999999999999)],
            "data_types": ["textbox", "textbox", "slider", "slider", "slider", "slider", "slider", "checkbox", "number"],
            "url_processor": lambda url: url,
            "output_parser": lambda data: data.get("output")['data'][0][0]["image"]["url"]
        }
    }

    def __init__(self, cookie: str = ""):
        self.cookie = cookie
        self.api_base = "https://s5k.cn"  # ModelScope API base URL

    async def _get_modelscope_token(self, session: aiohttp.ClientSession, headers: Dict[str, str]) -> str:
        """获取ModelScope token"""
        async with session.get(
            f"https://modelscope.cn/api/v1/studios/token",
            headers=headers
        ) as response:
            response.raise_for_status()
            token_data = await response.json()
            return token_data["Data"]["Token"]

    async def generate_modelscope(self, model: str, prompt: str, width: int, height: int) -> str:
        """使用ModelScope模型生成图片"""
        if model not in self.MODELSCOPE_MODELS:
            raise ValueError(f"Unsupported ModelScope model: {model}")

        model_config = self.MODELSCOPE_MODELS[model]
        headers = {
            "User-Agent": "Mozilla/5.0 (Windows NT 10.0; Win64; x64) AppleWebKit/537.36 (KHTML, like Gecko) Chrome/121.0.0.0 Safari/537.36",
            "Cookie": self.cookie
        }

        async with aiohttp.ClientSession() as session:
            # 获取 token
            studio_token = await self._get_modelscope_token(session, headers)
            headers["X-Studio-Token"] = studio_token
            session_hash = ''.join(random.choices('abcdefghijklmnopqrstuvwxyz', k=7))

            # 调用模型生成图片
            model_url = f"{self.api_base}/api/v1/studio/{model_config['path']}/gradio/queue/join"
            params = {
                "backend_url": f"/api/v1/studio/{model_config['path']}/gradio/",
                "sdk_version": "4.31.3",
                "studio_token": studio_token
            }

            json_data = {
                "data": model_config["data_builder"](height, width, prompt),
                "fn_index": model_config["fn_index"],
                "trigger_id": model_config["trigger_id"],
                "dataType": model_config["data_types"],
                "session_hash": session_hash
            }

            async with session.post(
                model_url,
                headers=headers,
                params=params,
                json=json_data
            ) as response:
                response.raise_for_status()
                data = await response.json()
                event_id = data["event_id"]

            # 获取结果
            result_url = f"{self.api_base}/api/v1/studio/{model_config['path']}/gradio/queue/data"
            params = {
                "session_hash": session_hash,
                "studio_token": studio_token
            }

            async with session.get(result_url, headers=headers, params=params) as response:
                response.raise_for_status()
                async for line in response.content:
                    line = line.decode('utf-8')
                    if line.startswith('data: '):
                        logger.debug(line)
                        event_data = json.loads(line[6:])
                        if event_data["event_id"] == event_id and event_data["msg"] == "process_completed":
                            try:
                                url = model_config["output_parser"](event_data)
                                if url:
                                    return model_config["url_processor"](url)
                            except Exception as e:
                                logger.error(f"Failed to parse output for model {model}: {e}")
            return ""

    async def generate_shakker(self, model: str, prompt: str, width: int, height: int) -> str:
        """使用Shakker平台生成图片"""
        # Model mapping for Shakker platform
        MODEL_MAPPING = {
            "anime": 1489127,
            "photo": 1489700
        }

        if model not in MODEL_MAPPING:
            raise ValueError(f"Unsupported Shakker model: {model}")

        # Adjust dimensions if they exceed 1024
        if width >= height and width > 1024:
            height = int(1024 * height / width)
            width = 1024
        elif height > width and height > 1024:
            width = int(1024 * width / height)
            height = 1024

        # Prepare request payload
        json_data = {
            "source": 3,
            "adetailerEnable": 0,
            "mode": 1,
            "projectData": {
                "style": "",
                "baseType": 3,
                "presetBaseModelId": "photography",
                "baseModel": None,
                "loraModels": [],
                "width": int(width * 1.5),
                "height": int(height * 1.5),
                "isFixedRatio": True,
                "hires": True,
                "count": 1,
                "prompt": prompt,
                "negativePrompt": "",
                "presetNegativePrompts": ["common", "bad_hand"],
                "samplerMethod": "29",
                "samplingSteps": 20,
                "seedType": "0",
                "seedNumber": -1,
                "vae": "-1",
                "cfgScale": 7,
                "clipSkip": 2,
                "controlnets": [],
                "checkpoint": None,
                "hiresOptions": {
                    "enabled": True,
                    "scale": 1.5,
                    "upscaler": "11",
                    "strength": 0.5,
                    "steps": 20,
                    "width": width,
                    "height": height
                },
                "modelCfgScale": 7,
                "changed": True,
                "modelGroupCoverUrl": None,
                "addOns": [],
                "mode": 1,
                "isSimpleMode": False,
                "generateType": "normal",
                "renderWidth": int(width * 1.5),
                "renderHeight": int(height * 1.5),
                "samplerMethodName": "Restart"
            },
            "vae": "",
            "checkpointId": MODEL_MAPPING[model],
            "additionalNetwork": [],
            "generateType": 1,
            "text2img": {
                "width": width,
                "height": height,
                "prompt": prompt,
                "negativePrompt": ",lowres, normal quality, worst quality, cropped, blurry, drawing, painting, glowing",
                "samplingMethod": "29",
                "samplingStep": 20,
                "batchSize": 1,
                "batchCount": 1,
                "cfgScale": 7,
                "clipSkip": 2,
                "seed": -1,
                "tiling": 0,
                "seedExtra": 0,
                "restoreFaces": 0,
                "hiResFix": 1,
                "extraNetwork": [],
                "promptRecommend": True,
                "hiResFixInfo": {
                    "upscaler": 11,
                    "upscaleBy": 1.5,
                    "resizeWidth": int(width * 1.5),
                    "resizeHeight": int(height * 1.5)
                },
                "hiresSteps": 20,
                "denoisingStrength": 0.5
            },
            "cid": f"{int(time.time() * 1000)}woivhqlb"
        }

        headers = {"Token": self.cookie}  # Using cookie as token

        async with aiohttp.ClientSession() as session:
            # Submit generation request
            async with session.post(
                "https://www.shakker.ai/gateway/sd-api/gen/tool/shake",
                json=json_data,
                headers=headers
            ) as response:
                response.raise_for_status()
                data = await response.json()
                task_id = data["data"]

            # Wait for initial processing
            await asyncio.sleep(10)

            # Poll for results
            for _ in range(60):
                async with session.post(
                    f"https://www.shakker.ai/gateway/sd-api/generate/progress/msg/v1/{task_id}",
                    json={"flag": 3},
                    headers=headers
                ) as response:
                    response.raise_for_status()
                    result = await response.json()

                    if result["data"]["percentCompleted"] == 100:
                        return result["data"]["images"][0]["previewPath"]

                await asyncio.sleep(1)

            return ""

    async def generate_image(self, platform: str, model: str, prompt: str, width: int, height: int) -> str:
        """统一的图片生成入口"""
        if platform == "modelscope":
            if not self.cookie:
               return "请前往https://modelscope.cn/登录后获取token(按F12-应用-cookie中的m_session_id)";
            if not self.cookie.startswith("m_session_id="):
                self.cookie = "m_session_id=" + self.cookie
            return await self.generate_modelscope(model, prompt, width, height)
        elif platform == "shakker":
            if not self.cookie:
                return "请前往https://www.shakker.ai/登录后获取token(按F12-应用-cookie中的usertoken)";
            return await self.generate_shakker(model, prompt, width, height)

        raise ValueError(f"Unsupported platform ({platform}) or model ({model})")
