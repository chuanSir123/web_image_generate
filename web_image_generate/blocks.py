from typing import Any, Dict, List, Optional,Annotated
from kirara_ai.workflow.core.block import Block, Input, Output, ParamMeta

from kirara_ai.im.message import IMMessage, TextMessage, ImageMessage
from kirara_ai.im.sender import ChatSender
from .image_generator import WebImageGenerator
import asyncio
from kirara_ai.logger import get_logger
from kirara_ai.ioc.container import DependencyContainer
import os
import yaml

logger = get_logger("ImageGenerator")
def get_image_platform_options_provider(container: DependencyContainer, block: Block) -> List[str]:
    return ["modelscope", "shakker"]
def get_options_provider(container: DependencyContainer, block: Block) -> List[str]:
    return ["flux", "ketu", "anime", "photo"]
class WebImageGenerateBlock(Block):
    """图片生成Block"""
    name = "text_to_image"
    description = "文生图，通过英文提示词生成图片"
    # 平台和对应的模型配置
    PLATFORM_MODELS = {
        "modelscope": ["flux", "ketu"],
        "shakker": ["anime", "photo"]
    }

    inputs = {
        "prompt": Input(name="prompt", label="提示词", data_type=str, description="文生图的英文提示词"),
        "width": Input(name="width", label="宽度", data_type=int, description="图片宽度", nullable=True, default=1024),
        "height": Input(name="height", label="高度", data_type=int, description="图片高度", nullable=True, default=1024),
        "cookie": Input(name="cookie", label="cookie", data_type=str, description="生图需要的cookie", nullable=True)
    }

    outputs = {
        "image_url": Output(name="image_url", label="图片URL", data_type=str, description="生成的图片URL")
    }

    def __init__(
        self,
        name: str = None,
        platform: Annotated[Optional[str],ParamMeta(label="平台", description="要使用的画图平台", options_provider=get_image_platform_options_provider),] = "modelscope",
        model: Annotated[Optional[str],ParamMeta(label="平台", description="要使用的画图平台", options_provider=get_options_provider),] = "flux",
        cookie: str = ""
    ):
        super().__init__(name)

        # 验证平台和模型的合法性
        if platform not in self.PLATFORM_MODELS:
            supported_platforms = ", ".join(self.PLATFORM_MODELS.keys())
            logger.error(f"不支持的平台 '{platform}'。支持的平台有: {supported_platforms}")
            raise ValueError(f"不支持的平台 '{platform}'。支持的平台有: {supported_platforms}")

        if model not in self.PLATFORM_MODELS[platform]:
            supported_models = ", ".join(self.PLATFORM_MODELS[platform])
            logger.error(f"平台 '{platform}' 不支持模型 '{model}'。支持的模型有: {supported_models}")
            raise ValueError(f"平台 '{platform}' 不支持模型 '{model}'。支持的模型有: {supported_models}")

        self.platform = platform
        self.model = model
        self.cookie = cookie
        self.generator = WebImageGenerator()
        self.config_path = os.path.join(os.path.dirname(__file__), "config.yaml")

    def _load_config(self):
        """从配置文件加载cookie"""
        try:
            if os.path.exists(self.config_path):
                with open(self.config_path, 'r', encoding='utf-8') as f:
                    config = yaml.safe_load(f) or {}
                    return config.get('cookies', {})
            return {}
        except Exception as e:
            logger.error(f"加载配置文件失败: {str(e)}")
            return {}

    def _save_config(self, cookies):
        """保存cookie到配置文件"""
        try:
            config = {'cookies': cookies}
            with open(self.config_path, 'w', encoding='utf-8') as f:
                yaml.dump(config, f, allow_unicode=True)
        except Exception as e:
            logger.error(f"保存配置文件失败: {str(e)}")

    def execute(self, **kwargs) -> Dict[str, Any]:
        prompt = kwargs.get("prompt", "")
        width = int(kwargs.get("width") or 1024)
        height = int(kwargs.get("height") or 1024)
        cookie_input = kwargs.get("cookie", "")

        # 如果传入了cookie，优先使用传入的cookie
        if cookie_input:
            self.cookie = cookie_input

        # 如果cookie为空，从配置文件加载
        if not self.cookie:
            cookies = self._load_config()
            self.cookie = cookies.get(self.platform, "")

        # 如果cookie仍然为空，返回平台特定的提示信息
        if not self.cookie:
            if self.platform == "modelscope":
                return {"image_url": "生成图片失败，请提醒用户前往https://modelscope.cn/登录后获取token并发送(按F12-应用-cookie中的m_session_id)"}
            elif self.platform == "shakker":
                return {"image_url": "生成图片失败，请提醒用户前往https://www.shakker.ai/登录后获取token并发送(按F12-应用-cookie中的usertoken)"}

        # 根据平台格式化cookie
        if self.platform == "modelscope" and not self.cookie.startswith("m_session_id="):
            self.cookie = "m_session_id=" + self.cookie

        try:
            try:
                loop = asyncio.get_event_loop()
            except RuntimeError:
                loop = asyncio.new_event_loop()
                asyncio.set_event_loop(loop)
            self.generator.cookie = self.cookie
            image_url = loop.run_until_complete(
                self.generator.generate_image(
                    platform=self.platform,
                    model=self.model,
                    prompt=prompt,
                    width=width,
                    height=height
                )
            )

            # 生成成功后，保存cookie到配置文件
            if image_url:
                cookies = self._load_config()
                cookies[self.platform] = self.cookie
                self._save_config(cookies)

            return {"image_url": image_url}
        except Exception as e:
            return {"image_url": f"生成失败: {str(e)}"}
class ImageToVideoGenerateBlock(Block):
    """图生视频生成Block"""
    name = "image_to_video"
    description = "图生视频，通过英文提示词和图片生成视频"

    inputs = {
        "prompt": Input(name="prompt", label="提示词", data_type=str, description="英文提示词"),
        "image_url": Input(name="image_url", label="图片url", data_type=str, description="图片url"),
        "second": Input(name="second", label="视频时长", data_type=int, description="视频时长", nullable=True, default=4),
        "cookie": Input(name="cookie", label="cookie", data_type=str, description="魔搭平台的cookie", nullable=True)
    }

    outputs = {
        "video_url": Output(name="video_url", label="视频URL", data_type=str, description="生成的视频URL")
    }

    def __init__(
        self,
        name: str = None,
        cookie: str = ""
    ):
        super().__init__(name)


        self.cookie = cookie
        self.generator = WebImageGenerator()
        self.config_path = os.path.join(os.path.dirname(__file__), "config.yaml")

    def _load_config(self):
        """从配置文件加载cookie"""
        try:
            if os.path.exists(self.config_path):
                with open(self.config_path, 'r', encoding='utf-8') as f:
                    config = yaml.safe_load(f) or {}
                    return config.get('cookies', {})
            return {}
        except Exception as e:
            logger.error(f"加载配置文件失败: {str(e)}")
            return {}

    def _save_config(self, cookies):
        """保存cookie到配置文件"""
        try:
            config = {'cookies': cookies}
            with open(self.config_path, 'w', encoding='utf-8') as f:
                yaml.dump(config, f, allow_unicode=True)
        except Exception as e:
            logger.error(f"保存配置文件失败: {str(e)}")

    def execute(self, **kwargs) -> Dict[str, Any]:
        image_url = kwargs.get("image_url", "")
        prompt = kwargs.get("prompt", "")
        second = int(kwargs.get("second") or 4)
        cookie_input = kwargs.get("cookie", "")

        # 如果传入了cookie，优先使用传入的cookie
        if cookie_input:
            self.cookie = cookie_input

        # 如果cookie为空，从配置文件加载
        if not self.cookie:
            cookies = self._load_config()
            self.cookie = cookies.get("modelscope", "")

        # 如果cookie仍然为空，返回平台特定的提示信息
        if not self.cookie:
            return {"video_url": "生成视频失败，请提醒用户前往https://modelscope.cn/登录后获取token并发送(按F12-应用-cookie中的m_session_id)"}


        # 根据平台格式化cookie
        if not self.cookie.startswith("m_session_id="):
            self.cookie = "m_session_id=" + self.cookie

        try:
            try:
                loop = asyncio.get_event_loop()
            except RuntimeError:
                loop = asyncio.new_event_loop()
                asyncio.set_event_loop(loop)
            self.generator.cookie = self.cookie
            video_url = loop.run_until_complete(
                self.generator.generate_imageToVideo(
                    image_url=image_url,
                    prompt=prompt,
                    second=second
                )
            )

            # 生成成功后，保存cookie到配置文件
            if video_url:
                cookies = self._load_config()
                cookies["modelscope"] = self.cookie
                self._save_config(cookies)

            return {"video_url": video_url}
        except Exception as e:
            return {"video_url": f"生成失败: {str(e)}"}
class ImageUrlToIMMessage(Block):
    """纯文本转 IMMessage"""

    name = "imageUrl_to_im_message"
    container: DependencyContainer
    inputs = {"image_url": Input("image_url", "图片url", str, "图片url")}
    outputs = {"msg": Output("msg", "IM 消息", IMMessage, "IM 消息")}

    def __init__(self):
        self.split_by = ","

    def execute(self, image_url: str) -> Dict[str, Any]:
        if not image_url.startswith("http"):
            return {"msg": IMMessage(sender=ChatSender.get_bot_sender(), message_elements=[TextMessage(image_url)])}
        if self.split_by:
            return {"msg": IMMessage(sender=ChatSender.get_bot_sender(), message_elements=[ImageMessage(line) for line in image_url.split(self.split_by)])}
        else:
            return {"msg": IMMessage(sender=ChatSender.get_bot_sender(), message_elements=[ImageMessage(image_url)])}

class TextToMusicGenerateBlock(Block):
    """文生音乐生成Block"""
    name = "text_to_music"
    description = "文生音乐（生成歌曲），通过时长、歌词和风格生成音乐"

    inputs = {
        "lyrics": Input(name="lyrics", label="歌词", data_type=str, description="歌词内容,示例如下:[verse]\nNeon lights they flicker bright\nCity hums in dead of night\nRhythms pulse through concrete veins\nLost in echoes of refrains\n[verse]\nBassline groovin' in my chest\nHeartbeats match the city's zest\nElectric whispers fill the air\nSynthesized dreams everywhere\n[chorus]\nTurn it up and let it flow\nFeel the fire let it grow\nIn this rhythm we belong\nHear the night sing out our song\n[verse]\nGuitar strings they start to weep\nWake the soul from silent sleep\nEvery note a story told\nIn this night we’re bold and gold[bridge]\nVoices blend in harmony\nLost in pure cacophony\nTimeless echoes timeless cries\nSoulful shouts beneath the skies\n[verse]\nKeyboard dances on the keys\nMelodies on evening breeze\nCatch the tune and hold it tight\nIn this moment we take flight"),
        "style": Input(name="style", label="风格", data_type=str, description="音乐风格，示例如下:rock, hip - hop, orchestral, bass, drums, electric guitar, piano, synthesizer, violin, viola, cello, fast, energetic, motivational, inspirational, empowering", nullable=True,default="rock, hip - hop, orchestral, bass, drums, electric guitar, piano, synthesizer, violin, viola, cello, fast, energetic, motivational, inspirational, empowering"),
    }

    outputs = {
        "music_url": Output(name="music_url", label="音乐URL", data_type=str, description="生成的音乐URL")
    }

    def __init__(self, name: str = None, cookie: str = ""):
        super().__init__(name)
        self.cookie = cookie
        self.generator = WebImageGenerator()
        self.config_path = os.path.join(os.path.dirname(__file__), "config.yaml")

    def _load_config(self):
        try:
            if os.path.exists(self.config_path):
                with open(self.config_path, 'r', encoding='utf-8') as f:
                    config = yaml.safe_load(f) or {}
                    return config.get('cookies', {})
            return {}
        except Exception as e:
            logger.error(f"加载配置文件失败: {str(e)}")
            return {}

    def _save_config(self, cookies):
        try:
            config = {'cookies': cookies}
            with open(self.config_path, 'w', encoding='utf-8') as f:
                yaml.dump(config, f, allow_unicode=True)
        except Exception as e:
            logger.error(f"保存配置文件失败: {str(e)}")

    def execute(self, **kwargs) -> Dict[str, Any]:
        import asyncio
        duration = -1
        lyrics = kwargs.get("lyrics", "")
        style = kwargs.get("style", "")
        cookie_input = kwargs.get("cookie", "")

        # 如果传入了cookie，优先使用传入的cookie
        if cookie_input:
            self.cookie = cookie_input

        # 如果cookie为空，从配置文件加载
        if not self.cookie:
            cookies = self._load_config()
            self.cookie = cookies.get("modelscope", "")

        # 如果cookie仍然为空，返回平台特定的提示信息
        if not self.cookie:
            return {"music_url": "生成音乐失败，请提醒用户前往https://modelscope.cn/登录后获取token并发送(按F12-应用-cookie中的m_session_id)"}

        # 根据平台格式化cookie
        if not self.cookie.startswith("m_session_id="):
            self.cookie = "m_session_id=" + self.cookie

        self.generator.cookie = self.cookie
        try:
            try:
                loop = asyncio.get_event_loop()
            except RuntimeError:
                loop = asyncio.new_event_loop()
                asyncio.set_event_loop(loop)
            url = loop.run_until_complete(self.generator.generate_music(duration, lyrics, style))
            # 生成成功后，保存cookie到配置文件
            if url and url.startswith("http"):
                cookies = self._load_config()
                cookies["modelscope"] = self.cookie
                self._save_config(cookies)
            if url:
                return {"music_url": url,"lyrics":lyrics}
            else:
                return {"music_url": "生成失败，未获取到音乐URL"}
        except Exception as e:
            return {"music_url": f"生成失败: {str(e)}"}
