"""Agent tool for reading and updating the current chat session info."""

from chat.agent.tools.base import Tool, ToolContext, ToolResult
from models.dto import ChatDTO
from repository.chat import ChatRepository


class ChatInfoTool(Tool):
    """Read or update the current chat session's metadata (name, etc.)."""

    name = "chat_info"
    description = (
        "读取或修改当前聊天会话的信息。"
        "不带参数调用时返回当前会话的名称、创建时间、消息数等信息；"
        "传入 new_name 参数时可修改会话标题。"
    )
    input_schema = {
        "type": "object",
        "properties": {
            "new_name": {
                "type": "string",
                "description": "新的会话标题。不传则仅读取当前会话信息。",
            },
        },
    }
    preserve_in_compact = True

    async def run(self, ctx: ToolContext, **kwargs) -> ToolResult:
        new_name = kwargs.get("new_name")
        repo = ChatRepository()

        try:
            chat = repo.get_by_id(ctx.chat_id)
            if not chat:
                return ToolResult(
                    content=f"Error: chat {ctx.chat_id} not found",
                    is_error=True,
                )

            # Read mode
            if not new_name:
                lines = [
                    f"chat_id: {chat.id}",
                    f"name: {chat.name}",
                    f"created_at: {chat.created_at}",
                    f"message_count: {chat.message_count or 0}",
                    f"collection_ids: {chat.collection_ids}",
                ]
                if chat.bound_collection_id:
                    lines.append(f"bound_collection_id: {chat.bound_collection_id}")
                return ToolResult(content="\n".join(lines))

            # Update mode
            new_name = new_name.strip()
            if not new_name:
                return ToolResult(
                    content="Error: new_name cannot be empty",
                    is_error=True,
                )

            updated = repo.update_by_model(ChatDTO(id=ctx.chat_id, name=new_name))
            if not updated:
                return ToolResult(
                    content=f"Error: failed to update chat {ctx.chat_id}",
                    is_error=True,
                )

            return ToolResult(
                content=f"会话标题已更新为: {new_name}",
                structured={"new_name": new_name},
            )
        except Exception as exc:
            return ToolResult(content=f"Error: {exc}", is_error=True)
