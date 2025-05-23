import aiohttp
import random
import json
import time
import asyncio
from typing import Dict, Any, Optional, Tuple
from kirara_ai.logger import get_logger
from gradio_client import Client, handle_file
import tempfile
import os
import io
from curl_cffi import AsyncSession, Response
import mimetypes
import random
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
        aspect_ratio = width / height
        # 确保宽度和高度的最小值至少是1024
        if min(height, width) < 1024:
            if height < width:
                height = 1024
                width = (int(height * aspect_ratio/64))*64
            else:
                width = 1024
                height = (int(width / aspect_ratio/64))*64

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
        if "-ketu" in prompt and platform == "modelscope":
            prompt = prompt.replace("-ketu","")
            model = "ketu"
        elif "-flux" in prompt  and platform == "modelscope":
            prompt = prompt.replace("-flux","")
            model = "flux"
        elif "-anime" in prompt and platform == "shakker":
            prompt = prompt.replace("-anime","")
            model = "anime"
        elif "-photo" in prompt and platform == "shakker":
            prompt = prompt.replace("-photo","")
            model = "photo"
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

    async def generate_imageToVideo(self,image_url: str, prompt: str, second: int) -> str:

        if not self.cookie:
            return "请前往https://modelscope.cn/登录后获取token(按F12-应用-cookie中的m_session_id)";
        if not self.cookie.startswith("m_session_id="):
            self.cookie = "m_session_id=" + self.cookie
        width = 480
        height = 832

        headers = {
            "User-Agent": "Mozilla/5.0 (Windows NT 10.0; Win64; x64) AppleWebKit/537.36 (KHTML, like Gecko) Chrome/121.0.0.0 Safari/537.36",
            "Cookie": self.cookie
        }
        async with AsyncSession(trust_env=True, timeout=3000) as session:
            resp: Response = await session.get(image_url, impersonate="chrome101")
        image_bytes = resp.content
        with tempfile.NamedTemporaryFile(delete=False, suffix='.jpg') as temp_file:
            temp_file.write(image_bytes)
            temp_path = temp_file.name
        async with aiohttp.ClientSession() as session:
            studio_token = await self._get_modelscope_token(session, headers)

            # Create client with custom headers containing the cookie
            headers = {
                "Cookie": f"studio_token={studio_token}",
                "x-studio-token": studio_token
            }
            logger.debug(headers)

            try:
                # Upload image
                file_path = await self._upload_image(temp_path, headers,"chuansir-teacache4wan2-1-i2v-720p-fp8")

                # Process video
                video_url = await self._process_video(file_path, prompt,second, headers,"chuansir-teacache4wan2-1-i2v-720p-fp8")

                # Save cookie if successful
                if video_url:
                    return {"video_url": video_url}
            except Exception as e:
                # Upload image
                file_path = await self._upload_image(temp_path, headers)

                # Process video
                video_url = await self._process_video(file_path, prompt,second, headers)

                # Save cookie if successful
                if video_url:
                    return {"video_url": video_url}
            finally:
                # 删除临时文件
                os.remove(temp_path)


    async def _upload_image(self, image_path: str, headers: dict,space_name :str = "chuansir-framepack") -> str:
        """Upload image and return the file path"""
        # Generate upload ID
        upload_id = "".join(random.choices("abcdefghijklmnopqrstuvwxyz0123456789", k=10))

        # Create form data without specifying boundary
        form = aiohttp.FormData()
        form.add_field('files',
                       open(image_path, 'rb'),
                       filename=os.path.basename(image_path),
                       content_type=mimetypes.guess_type(image_path)[0] or 'application/octet-stream')

        # Copy headers for upload
        upload_headers = headers.copy()
        # Let aiohttp handle the content-type header for the form data

        # Upload file
        upload_url = f"https://{space_name}.ms.show/gradio_api/upload?upload_id={upload_id}"
        async with aiohttp.ClientSession() as session:
            async with session.post(upload_url, data=form, headers=upload_headers) as response:
                response.raise_for_status()
                file_paths = await response.json()

            # Wait for upload to complete
            progress_url = f"https://{space_name}.ms.show/gradio_api/upload_progress?upload_id={upload_id}"
            while True:
                async with session.get(progress_url, headers=headers) as response:
                    # Handle event-stream format
                    progress_text = await response.text()
                    if "done" in progress_text:
                        break
                    await asyncio.sleep(0.5)
        return file_paths[0]

    async def _process_video(self, file_path: str, english_prompt: str,second: int, headers: dict,space_name :str = "chuansir-framepack") -> str:
        """Process video generation and return video URL"""


        # Join queue
        queue_url = f"https://{space_name}.ms.show/gradio_api/queue/join?t={int(time.time()*1000)}&__theme=light&studio_token={headers['x-studio-token']}&backend_url=/"

        session_hash = "".join(random.choices("abcdefghijklmnopqrstuvwxyz0123456789", k=10))

        payload = {
            "data": [
                {
                    "path": file_path,
                    "url": f"https://{space_name}.ms.show/gradio_api/file={file_path}",
                    "orig_name": file_path.split('/')[-1],
                    "mime_type": "image/png",
                    "meta": {"_type": "gradio.FileData"}
                },
                english_prompt,
                "",
                31337,
                second,
                9,
                25,
                1,
                10,
                0,
                6,
                True,
                16,
                18,
                None
            ],
            "event_data": None,
            "fn_index": 1,
            "trigger_id": 8,
            "dataType": ["image","textbox","textbox","number","slider","slider","slider","slider","slider","slider","slider","checkbox","slider","slider","state"],
            "session_hash": session_hash
        }
        if "chuansir-framepack" != space_name:
            payload["data"].pop(-1)
            payload["dataType"].pop(-1)
        videoUrl = ""
        async with aiohttp.ClientSession() as session:
            # Join the queue
            async with session.post(queue_url, json=payload, headers=headers) as response:
                response.raise_for_status()
                queue_data = await response.json()
                event_id = queue_data["event_id"]
                logger.debug(f"event_id:{event_id}")


        # Stream for status updates
            status_url = f"https://{space_name}.ms.show/gradio_api/queue/data?session_hash={session_hash}&studio_token={headers['x-studio-token']}"

            # 处理事件流
            async with session.get(status_url, headers=headers,timeout=aiohttp.ClientTimeout(total=6000)) as response:
                response.raise_for_status()

                # 使用流式读取
                async for line in response.content:
                    line = line.decode('utf-8').strip()
                    logger.debug(line)
                    # 事件流格式为 "data: {...}"
                    if line.startswith('data:'):
                        try:
                            data_str = line[5:].strip()  # 去掉 "data: " 前缀
                            if data_str:
                                data = json.loads(data_str)
                                if data.get("msg") == "process_generating" and "output" in data and data.get("event_id") == event_id and "data" in data["output"] and  data["output"]["data"][0] :
                                    # 找到完成的结果
                                    videoUrl =  data["output"]["data"][0][1][2]["url"]
                                if data.get("msg") == "process_completed" and "output" in data and data.get("event_id") == event_id and "data" in data["output"]:
                                    # 找到完成的结果
                                    return data["output"]["data"][0]["video"]["url"]
                        except json.JSONDecodeError:
                            continue
                        except Exception as e:
                            logger.error(f"处理事件流时出错: {str(e)}")
        if videoUrl:
            return videoUrl
        # 如果没有找到结果，返回错误信息
        raise Exception("处理超时或未能获取结果")

    async def generate_music(self, duration: int, lyrics: str, style: str) -> str:
        """文生音乐生成，流程与generate_imageToVideo一致，返回音乐url"""
        if not self.cookie:
            return "请前往https://modelscope.cn/登录后获取token(按F12-应用-cookie中的m_session_id)"
        if not self.cookie.startswith("m_session_id="):
            self.cookie = "m_session_id=" + self.cookie

        headers = {
            "User-Agent": "Mozilla/5.0 (Windows NT 10.0; Win64; x64) AppleWebKit/537.36 (KHTML, like Gecko) Chrome/121.0.0.0 Safari/537.36",
            "Cookie": self.cookie
        }
        async with aiohttp.ClientSession() as session:
            studio_token = await self._get_modelscope_token(session, headers)
            # 构造headers
            headers = {
                "Cookie": f"studio_token={studio_token}",
                "x-studio-token": studio_token
            }
            join_url = "https://ace-step-ace-step.ms.show/gradio_api/queue/join"
            data_url = "https://ace-step-ace-step.ms.show/gradio_api/queue/data"
            session_hash = "".join(random.choices("abcdefghijklmnopqrstuvwxyz0123456789", k=10))
            # 构造data参数
            data = [duration, style, lyrics, 27, 15, "euler", "apg", 10, "", 0.5, 0, 3, True, True, True, "", 0, 0]
            payload = {
                "data": data,
                "event_data": None,
                "fn_index": 9,
                "trigger_id": 30,
                "dataType": [
                    "slider", "textbox", "textbox", "slider", "slider", "radio", "radio", "slider", "textbox", "slider", "slider", "slider", "checkbox", "checkbox", "checkbox", "textbox", "slider", "slider"
                ],
                "session_hash": session_hash
            }
            logger.debug(payload)
            # join queue
            async with session.post(join_url, json=payload, headers=headers) as resp:
                resp.raise_for_status()
                join_data = await resp.json()
                event_id = join_data.get("event_id")
            # poll data
            params = {"session_hash": payload["session_hash"], "studio_token": studio_token}
            async with session.get(data_url, params=params, headers=headers) as resp:
                async for line in resp.content:
                    line = line.decode("utf-8").strip()
                    if line.startswith("data:"):
                        try:
                            data_str = line[5:].strip()
                            if data_str:
                                data = json.loads(data_str)
                                if data.get("msg") == "process_completed" and "output" in data and "data" in data["output"] and data.get("event_id") == event_id:
                                    # 提取url
                                    url = data["output"]["data"][0]["url"]
                                    return url
                        except Exception:
                            continue
        return None
