from setuptools import setup, find_packages
import io
import os

version = os.environ.get('RELEASE_VERSION', '0.3.2'
'').lstrip('v')

setup(
    name="chatgpt-mirai-qq-bot-web-image-generate",
    version=version,
    packages=find_packages(),
    include_package_data=True,  # 这行很重要
    package_data={
        "web_image_generate": ["example/*.yaml", "example/*.yml"],
    },
    install_requires=[
        "kirara-ai>=3.2.0","gradio_client"
    ],
    entry_points={
        'chatgpt_mirai.plugins': [
            'web_image_generate = web_image_generate:WebImageGeneratePlugin'
        ]
    },
    author="chuanSir",
    author_email="416448943@qq.com",

    description="WebImageGeneratePlugin for lss233/chatgpt-mirai-qq-bot",
    long_description=io.open("README.md", encoding='utf-8').read(),
    long_description_content_type="text/markdown",
    url="https://github.com/chuanSir123/web_image_generate",
    classifiers=[
        "Programming Language :: Python :: 3",
        'License :: OSI Approved :: GNU Affero General Public License v3',
        "Operating System :: OS Independent",
    ],
    project_urls={
        "Bug Tracker": "https://github.com/chuanSir123/web_image_generate/issues",
        "Documentation": "https://github.com/chuanSir123/web_image_generate/wiki",
        "Source Code": "https://github.com/chuanSir123/web_image_generate",
    },
    python_requires=">=3.8",
)
