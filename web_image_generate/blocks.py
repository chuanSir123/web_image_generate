from typing import Any, Dict, List, Optional,Annotated
from kirara_ai.workflow.core.block import Block
from kirara_ai.workflow.core.block.input_output import Input, Output
from kirara_ai.im.message import IMMessage, TextMessage, ImageMessage
from kirara_ai.im.sender import ChatSender
from .image_generator import WebImageGenerator
import asyncio
from kirara_ai.logger import get_logger
from kirara_ai.ioc.container import DependencyContainer

logger = get_logger("ImageGenerator")
class WebImageGenerateBlock(Block):
    """图片生成Block"""
    name = "image_generate"

    # 平台和对应的模型配置
    PLATFORM_MODELS = {
        "modelscope": ["flux", "ketu"],
        "shakker": ["anime", "photo"]
    }

    inputs = {
        "prompt": Input(name="prompt", label="提示词", data_type=str, description="生成提示词"),
        "width": Input(name="width", label="宽度", data_type=int, description="图片宽度", nullable=True, default=1024),
        "height": Input(name="height", label="高度", data_type=int, description="图片高度", nullable=True, default=1024)
    }

    outputs = {
        "image_url": Output(name="image_url", label="图片URL", data_type=str, description="生成的图片URL")
    }

    def __init__(
        self,
        name: str = None,
        platform: str = "modelscope",
        model: str = "flux",
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
        self.generator = WebImageGenerator(cookie=cookie)

    def execute(self, **kwargs) -> Dict[str, Any]:
        prompt = kwargs.get("prompt", "")
        width = int(kwargs.get("width", 1024))
        height = int(kwargs.get("height", 1024))

        try:
            try:
                loop = asyncio.get_event_loop()
            except RuntimeError:
                loop = asyncio.new_event_loop()
                asyncio.set_event_loop(loop)

            image_url = loop.run_until_complete(
                self.generator.generate_image(
                    platform=self.platform,
                    model=self.model,
                    prompt=prompt,
                    width=width,
                    height=height
                )
            )
            return {"image_url": image_url}
        except Exception as e:
            return {"image_url": f"生成失败: {str(e)}"}

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
