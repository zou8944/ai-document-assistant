"""
文档摘要生成器模块
基于LLM为文档生成高质量摘要，支持不同文档类型的专门化处理
"""

import logging

from langchain_core.output_parsers import StrOutputParser
from langchain_core.prompts import ChatPromptTemplate
from langchain_openai import ChatOpenAI

logger = logging.getLogger(__name__)

DOC_SUMMARY_PROMPT = ChatPromptTemplate.from_template("""
请阅读以下文档内容，并用简洁的语言生成总结。总结长度约为 50 个字，需突出主要主题和关键信息。若原文不足 200 字，则直接输出原文。

---
{document_content}
""")

COLLECTION_SUMMARY_PROMPT = ChatPromptTemplate.from_template("""
如下是当前知识库各个文档的内容摘要，请基于此生成一份综合性的知识库总结，突出主要主题和关键信息，长度约为 500 字。

---
{document_contents}
""")


class DocumentSummarizer:
    """文档摘要生成器"""

    def __init__(self, llm: ChatOpenAI):
        self.llm = llm

    def summarize_document(self, content) -> str:
        prompt = DOC_SUMMARY_PROMPT
        chain = prompt | self.llm | StrOutputParser()
        return chain.invoke({"document_content": content})

    def summarize_collection(self, contents: list[str]) -> str:
        prompt = COLLECTION_SUMMARY_PROMPT
        chain = prompt | self.llm | StrOutputParser()
        document_contents = []
        for idx, content in enumerate(contents):
            document_contents.append(f"文档 {idx + 1}: {content}")
        return chain.invoke({"document_contents": "\n".join(document_contents)})


if __name__ == "__main__":
    import asyncio

    from langchain_openai import ChatOpenAI

    async def main():
        args = {
            "model": "deepseek-ai/DeepSeek-V3",
            "temperature": 0.1,
            "api_key": "sk-fyhyvwjkjxwgcllguegokxzjowkqsovpzhswashhqqsycefm",
            "base_url": "https://api.siliconflow.cn/v1"
        }
        llm = ChatOpenAI(**args)
        summarizer = DocumentSummarizer(llm)
        content = r"""
dddd
"""
        print(summarizer.summarize_document(content))

    asyncio.run(main())
