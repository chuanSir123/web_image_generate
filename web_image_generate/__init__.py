from typing import Dict, Any, List
from kirara_ai.plugin_manager.plugin import Plugin
from kirara_ai.logger import get_logger
from dataclasses import dataclass
from kirara_ai.workflow.core.block import BlockRegistry
from kirara_ai.ioc.inject import Inject
from kirara_ai.ioc.container import DependencyContainer
from kirara_ai.workflow.core.workflow.builder import WorkflowBuilder
from kirara_ai.workflow.core.workflow.registry import WorkflowRegistry
from .blocks import WebImageGenerateBlock,ImageUrlToIMMessage
logger = get_logger("WebImageGenerate")
import importlib.resources
import os
from pathlib import Path

class WebImageGeneratePlugin(Plugin):
    def __init__(self, block_registry: BlockRegistry, container: DependencyContainer):
        super().__init__()
        self.block_registry = block_registry
        self.workflow_registry = container.resolve(WorkflowRegistry)
        self.container = container

    def on_load(self):
        logger.info("ImageGeneratePlugin loading")

        # 注册Block
        try:
            self.block_registry.register("web_image_generate", "image", WebImageGenerateBlock)
            self.block_registry.register("image_url_to_imMessage", "image", ImageUrlToIMMessage)
        except Exception as e:
            logger.warning(f"ImageGeneratePlugin failed: {e}")

        try:
            # 获取当前文件的绝对路径
            with importlib.resources.path('web_image_generate', '__init__.py') as p:
                package_path = p.parent
                example_dir = package_path / 'example'

                # 确保目录存在
                if not example_dir.exists():
                    raise FileNotFoundError(f"Example directory not found at {example_dir}")

                # 获取所有yaml文件
                yaml_files = list(example_dir.glob('*.yaml')) + list(example_dir.glob('*.yml'))

                for yaml in yaml_files:
                    logger.info(yaml)
                    self.workflow_registry.register("image", yaml.stem, WorkflowBuilder.load_from_yaml(os.path.join(example_dir, yaml), self.container))
        except Exception as e:
            try:
                current_file = os.path.abspath(__file__)

                # 获取当前文件所在目录
                parent_dir = os.path.dirname(current_file)

                # 构建 example 目录的路径
                example_dir = os.path.join(parent_dir, 'example')
                # 获取 example 目录下所有的 yaml 文件
                yaml_files = [f for f in os.listdir(example_dir) if f.endswith('.yaml') or f.endswith('.yml')]

                for yaml in yaml_files:
                    logger.info(os.path.join(example_dir, yaml))
                    self.workflow_registry.register("image", yaml.stem, WorkflowBuilder.load_from_yaml(os.path.join(example_dir, yaml), self.container))
            except Exception as e:
                logger.warning(f"workflow_registry failed: {e}")

    def on_start(self):
        logger.info("ImageGeneratePlugin started")

    def on_stop(self):
        logger.info("ImageGeneratePlugin stopped")

