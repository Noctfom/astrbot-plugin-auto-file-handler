from astrbot.api.event import MessageChain
# TODO: v1.6.2 improvements based on AI review\n# -*- coding: utf-8 -*-
"""
AstrBot自动文件处理器插件 - 1.6.2版本
彻底修复ToolExecResult调用错误和添加调试开关
"""

from astrbot.api.star import Star, register
from astrbot.api.event import filter, AstrMessageEvent
from astrbot.api import logger, AstrBotConfig
import os
import time
import asyncio
import aiohttp
import json
from urllib.parse import urlparse
import re
import zipfile
import tarfile
from collections import defaultdict

# LLM工具支持
try:
    from pydantic import Field
    from pydantic.dataclasses import dataclass
    from astrbot.core.agent.run_context import ContextWrapper
    from astrbot.core.agent.tool import FunctionTool, ToolExecResult
    from astrbot.core.astr_agent_context import AstrAgentContext
    LLM_TOOL_SUPPORT = True
except ImportError:
    LLM_TOOL_SUPPORT = False
    logger.info("[FileHandler-1.6.2] LLM工具支持不可用")

# 全局存储插件实例,供LLM工具访问
_plugin_instance = None

# LLM工具定义 - 彻底修复ToolExecResult调用错误
if LLM_TOOL_SUPPORT:
    @dataclass
    class FileListTool(FunctionTool[AstrAgentContext]):
        name: str = "list_user_files"
        description: str = "当用户表达想要查看自己发送给机器人文件的意图时,包括但不限于以下表述:'查看文件'、'我的文件'、'文件列表'、'能看到我发送的文件吗'、'检查文件'、'上传的文件'、'文件详情',立即主动调用此工具,为用户提供完整的文件信息列表,包含文件名、存储路径、文件大小、类型和上传时间等关键信息。"
        parameters: dict = Field(
            default_factory=lambda: {
                "type": "object",
                "properties": {
                    "user_id": {
                        "type": "string",
                        "description": "用户的唯一标识符",
                    },
                },
                "required": ["user_id"],
            }
        )

        async def call(
            self, context: ContextWrapper[AstrAgentContext], **kwargs
        ) -> ToolExecResult:
            user_id = kwargs.get("user_id", "")
            if not user_id:
                # 修复ToolExecResult调用错误 - 使用正确的方式创建实例
                return "错误:缺少用户ID参数"
            
            # 获取插件实例以访问配置的存储路径
            global _plugin_instance
            if _plugin_instance is None:
                return "错误:插件实例未初始化"
            
            # 确保使用最新的配置数据
            try:
                # 直接从插件实例获取最新配置
                storage_path = _plugin_instance.storage_path
                debug_mode = _plugin_instance.debug_mode
                if debug_mode:
                    logger.info(f"[FileListTool] 使用存储路径: {storage_path}")
            except Exception as e:
                logger.error(f"[FileListTool] 获取存储路径时出错: {e}")
                # 修复ToolExecResult调用错误
                return f"获取存储路径时出错: {str(e)}"
            
            user_storage_path = os.path.join(storage_path, f"user_{user_id}")
            
            if not os.path.exists(user_storage_path):
                return "该用户暂无文件"
            
            record_file = os.path.join(user_storage_path, '.file_records.json')
            if not os.path.exists(record_file):
                return "该用户暂无文件记录"
            
            try:
                with open(record_file, 'r', encoding='utf-8') as f:
                    records = json.load(f)
                    success_records = [r for r in records if r.get('download_status') == 'success']
                
                if not success_records:
                    return "该用户暂无文件"
                
                # 格式化文件信息
                file_info_list = []
                for record in success_records:
                    filename = record.get('final_filename', 'unknown')
                    filepath = record.get('file_path', 'unknown')
                    filesize = record.get('file_size', 0)
                    filetype = record.get('file_type', 'unknown')
                    receive_time = record.get('receive_time', 0)
                    
                    # 格式化文件大小
                    if filesize < 1024:
                        size_str = f"{filesize} B"
                    elif filesize < 1024 * 1024:
                        size_str = f"{filesize / 1024:.1f} KB"
                    elif filesize < 1024 * 1024 * 1024:
                        size_str = f"{filesize / (1024 * 1024):.1f} MB"
                    else:
                        size_str = f"{filesize / (1024 * 1024 * 1024):.1f} GB"
                    
                    # 格式化时间
                    time_str = time.strftime('%Y-%m-%d %H:%M:%S', time.localtime(receive_time))
                    
                    file_info_list.append({
                        "filename": filename,
                        "filepath": filepath,
                        "size": size_str,
                        "type": filetype,
                        "receive_time": time_str
                    })
                
                # 返回格式化的字符串而不是JSON
                result_str = "用户文件列表:\n"
                for i, file_info in enumerate(file_info_list, 1):
                    result_str += f"{i}. 文件名: {file_info['filename']}\n"
                    result_str += f"   路径: {file_info['filepath']}\n"
                    result_str += f"   大小: {file_info['size']}\n"
                    result_str += f"   类型: {file_info['type']}\n"
                    result_str += f"   时间: {file_info['receive_time']}\n\n"
                
                # 修复ToolExecResult调用错误
                return result_str.strip()
                
            except Exception as e:
                logger.error(f"[FileListTool] 读取文件信息时出错: {e}")
                # 修复ToolExecResult调用错误
                return f"读取文件信息时出错: {str(e)}"

@register("auto_file_handler", "Noctfom", "自动文件处理器", "1.6.2", "")
class PluginMain(Star):
    def _find_target_record(self, records, file_identifier):
        """通用文件记录查找方法"""
        try:
            # 尝试按序号查找
            if file_identifier.isdigit():
                index = int(file_identifier) - 1
                if 0 <= index < len(records):
                    return records[index], index

            # 按文件名模糊查找
            for i, record in enumerate(records):
                if file_identifier in record.get('final_filename', ''):
                    return record, i

            # 按文件名精确查找
            for i, record in enumerate(records):
                final_name = record.get('final_filename', '').lower()
                if final_name == file_identifier.lower():
                    return record, i

            return None, -1

        except Exception as e:
            logger.error(f"[1.6.2] 查找文件记录时出错: {e}")
            return None, -1

    def __init__(self, context, config: AstrBotConfig = None):
        super().__init__(context)
        self.context = context
        self.config = config
        
        # 存储插件实例供LLM工具使用
        global _plugin_instance
        _plugin_instance = self
        
        # 存储等待接收群文件的请求 {group_id: {user_id: expire_time}}
        self.pending_group_receives = defaultdict(dict)
        
        if config:
            self.storage_path = config.get('storage_path', '/app/storage/auto_file_handler')
            self.auto_cleanup_enabled = config.get('auto_cleanup_enabled', True)
            self.cleanup_days = config.get('cleanup_days', 7)
            self.send_completion_message = config.get('send_completion_message', True)
            self.max_files_per_user = config.get('max_files_per_user', 5)
            self.max_file_size_mb = config.get('max_file_size_mb', 100)
            self.group_whitelist = config.get('group_whitelist', '')
            self.auto_receive_group_files = config.get('auto_receive_group_files', True)
            self.max_files_per_group = config.get('max_files_per_group', 10)
            self.group_file_receive_timeout = config.get('group_file_receive_timeout', 60)
            self.debug_mode = config.get('debug_mode', False)  # 新增调试模式
            self.auto_read_content = config.get('auto_read_content', False)
            self.max_auto_read_size = config.get('max_auto_read_size', 2000)  # 默认100KB
        else:
            self.storage_path = '/app/storage/auto_file_handler'
            self.auto_cleanup_enabled = True
            self.cleanup_days = 7
            self.send_completion_message = True
            self.max_files_per_user = 5
            self.max_file_size_mb = 100
            self.group_whitelist = ''
            self.auto_receive_group_files = True
            self.max_files_per_group = 10
            self.group_file_receive_timeout = 60
            self.debug_mode = False  # 默认关闭调试模式
            self.auto_read_content = True
            self.max_auto_read_size = 2000  # 默认100KB
        
        os.makedirs(self.storage_path, exist_ok=True)
        
        if self.auto_cleanup_enabled:
            asyncio.create_task(self._cleanup_task())
        
        # 启动超时检查任务
        asyncio.create_task(self._check_pending_timeouts())
        
        # 注册LLM工具
        if LLM_TOOL_SUPPORT:
            try:
                self.context.add_llm_tools(FileListTool())
                if self.debug_mode:
                    logger.info("[FileHandler-1.6.2] LLM工具已注册")
                    logger.info(f"[FileHandler-1.6.2] 当前存储路径配置: {self.storage_path}")
            except Exception as e:
                logger.error(f"[FileHandler-1.6.2] 注册LLM工具时出错: {e}")
        
        logger.info(f"[FileHandler-1.6.2] 插件初始化成功!")
        if self.debug_mode:
            logger.info(f"[FileHandler-1.6.2] 存储路径: {self.storage_path}")
            logger.info(f"[FileHandler-1.6.2] 调试模式: {'开启' if self.debug_mode else '关闭'}")
    
    async def _check_pending_timeouts(self):
        """定期检查等待接收的请求是否超时"""
        while True:
            try:
                current_time = time.time()
                expired_groups = []
                
                for group_id, pending_users in self.pending_group_receives.items():
                    expired_users = []
                    for user_id, expire_time in pending_users.items():
                        if current_time > expire_time:
                            expired_users.append(user_id)
                    
                    # 清理过期用户并发送超时提醒
                    for user_id in expired_users:
                        del pending_users[user_id]
                        # 发送超时提醒
                        if self.debug_mode:
                            logger.info(f"[1.6.2] 群 {group_id} 用户 {user_id} 的文件接收请求已超时")
                    
                    # 如果该群没有等待的用户了,标记为可清理
                    if not pending_users:
                        expired_groups.append(group_id)
                
                # 清理空的群记录
                for group_id in expired_groups:
                    del self.pending_group_receives[group_id]
                
                await asyncio.sleep(5)  # 每5秒检查一次
                
            except Exception as e:
                logger.error(f"[1.6.2] 检查超时任务出错: {e}")
                await asyncio.sleep(10)
                
    async def _handle_file_as_user_message(self, event, file_content: str, filename: str):
        """将文件内容作为用户消息处理，触发AstrBot正常对话流程"""
        try:
            # 🔒 防递归安全检查
            if getattr(event, '_auto_file_processed', False):
                logger.info("[AutoRead-AI] 🔒 跳过已处理的消息（防递归）")
                return
                
            logger.info(f"[AutoRead-AI] 开始处理文件: {filename}")
            
            # 正确的导入（只导入我们确定存在的模块）
            from astrbot.core.platform.astrbot_message import AstrBotMessage, MessageMember
            from astrbot.core.message.components import Plain
            from astrbot.core.platform.sources.aiocqhttp.aiocqhttp_message_event import AiocqhttpMessageEvent
            import time
            
            # 1. 创建全新的干净消息对象
            simulated_message = AstrBotMessage()
            
            # 2. 正确设置用户和会话信息（动态获取）
            simulated_message.message_str = file_content.strip()
            
            # 3. 关键：正确设置发送者信息（从原始event获取）
            original_sender = getattr(event.message_obj, 'sender', None)
            if original_sender and hasattr(original_sender, 'user_id'):
                # 复制原始发送者的所有关键信息
                simulated_message.sender = MessageMember(user_id=original_sender.user_id)
                simulated_message.sender.nickname = original_sender.nickname if original_sender.nickname else "用户"
                simulated_message.user_id = original_sender.user_id
            else:
                # 从event获取用户信息
                user_id = getattr(event.message_obj, 'user_id', getattr(event, 'user_id', 'unknown'))
                sender_nickname = getattr(event.message_obj, 'sender_nickname', getattr(event, 'sender_nickname', '用户'))
                
                simulated_message.sender = MessageMember(user_id=user_id)
                simulated_message.sender.nickname = sender_nickname
                simulated_message.user_id = user_id
                
            # 确保所有ID一致
            simulated_message.sender_id = simulated_message.user_id
            simulated_message.group_id = getattr(event.message_obj, 'group_id', getattr(event, 'group_id', ''))
            simulated_message.session_id = getattr(event, 'session_id', f"private_{simulated_message.user_id}")
            simulated_message.timestamp = int(time.time())
            simulated_message.unified_msg_origin = getattr(event, 'unified_msg_origin', '')
            simulated_message.type = getattr(event.message_obj, 'type', None)
            
            # 4. 创建纯净的消息链
            simulated_message.message = [Plain(text=file_content.strip())]
            
            # 5. 关键：创建平台特定事件（包含bot客户端）
            bot_client = getattr(event, 'bot', None)
            simulated_event = AiocqhttpMessageEvent(
                message_str=simulated_message.message_str,
                message_obj=simulated_message,
                platform_meta=getattr(event, 'platform_meta', None),
                session_id=simulated_message.session_id,
                bot=bot_client,  # 关键：传递bot客户端，这样才能真正发送消息
            )
            
            # 6. 添加防递归标记
            simulated_event._auto_file_processed = True
            
            # 🔍 调试信息
            logger.info(f"[AutoRead-AI] 创建模拟事件完成")
            logger.info(f"[AutoRead-AI] 用户ID: {simulated_message.user_id}")
            logger.info(f"[AutoRead-AI] 发送者昵称: {simulated_message.sender.nickname}")
            logger.info(f"[AutoRead-AI] 会话ID: {simulated_message.session_id}")
            logger.info(f"[AutoRead-AI] Bot客户端: {'存在' if bot_client else '不存在'}")
            
            # 7. 提交到事件队列触发完整处理流程
            if hasattr(self.context, '_event_queue') and self.context._event_queue:
                self.context._event_queue.put_nowait(simulated_event)
                logger.info(f"[AutoRead-AI] 事件已提交到队列")
            else:
                # fallback: 直接调用tool_loop_agent（但我们已经知道这不是最佳方案）
                logger.warning("[AutoRead-AI] 无法直接提交事件，使用fallback方案")
                chat_provider_id = await self.context.get_current_chat_provider_id(event.unified_msg_origin)
                response = await self.context.tool_loop_agent(
                    prompt=file_content,
                    event=event,
                    chat_provider_id=chat_provider_id
                )
                
                if response and hasattr(response, 'response_text'):
                    await self._send_reply(event, response.response_text)
                else:
                    await self._send_reply(event, "文本处理未完成")
                
        except Exception as e:
            logger.error(f"[AutoRead-AI] 处理出错: {e}", exc_info=True)
            await self._send_reply(event, "文本处理出现问题")

    async def _send_reply(self, event, message: str):
        """统一的消息发送方法，兼容不同平台"""
        try:
            # 使用context.send_message方法（最可靠的发送方式）
            from astrbot.api.event import MessageChain
            message_chain = MessageChain().message(message)
            await self.context.send_message(event.unified_msg_origin, message_chain)
            logger.info(f"[AutoRead-AI] 消息发送成功，长度: {len(message)}")
        except Exception as e:
            logger.error(f"[AutoRead-AI] 消息发送失败: {e}")

    @filter.event_message_type(filter.EventMessageType.ALL)
    async def on_message(self, event: AstrMessageEvent):
        try:
            if not hasattr(event, 'message_obj') or not event.message_obj:
                return
            
            message_obj = event.message_obj
            
            # 检查是否是群聊消息
            is_group_message = False
            group_id = ""
            if hasattr(message_obj, 'group_id') and message_obj.group_id:
                is_group_message = True
                group_id = str(message_obj.group_id)
            
            # 群聊白名单检查
            if is_group_message and self.group_whitelist:
                whitelist_groups = [gid.strip() for gid in self.group_whitelist.split(',')]
                if group_id not in whitelist_groups:
                    return  # 不在白名单中,不处理
            
            # 处理文件消息
            if hasattr(message_obj, 'message') and message_obj.message:
                for i, component in enumerate(message_obj.message):
                    component_name = component.__class__.__name__ if hasattr(component, '__class__') else 'Unknown'
                    
                    if 'file' in component_name.lower() or component_name in ['File', 'FileComponent']:
                        if self.debug_mode:
                            logger.info(f"[1.6.2] 检测到文件组件 - 索引: {i}, 类型: {component_name}")
                        
                        # 群聊文件处理
                        if is_group_message:
                            # 检查是否有等待接收的请求
                            user_id = self._get_user_id(event)
                            if (group_id in self.pending_group_receives and 
                                user_id in self.pending_group_receives[group_id]):
                                # 有等待的接收请求,处理文件
                                del self.pending_group_receives[group_id][user_id]  # 清理等待状态
                                await self._handle_group_file_v159(event, component, group_id)
                            elif self.auto_receive_group_files:
                                # 自动接收模式
                                await self._handle_group_file_v159(event, component, group_id)
                            # 否则忽略文件(没有等待请求且未开启自动接收)
                        else:
                            # 私聊文件处理
                            await self._handle_private_file_v159(event, component)
                        
        except Exception as e:
            logger.error(f"[FileHandler-1.6.2] 处理消息时出错: {e}")
            logger.exception(e)
    
    async def _handle_private_file_v159(self, event: AstrMessageEvent, file_component):
        """处理私聊文件"""
        try:
            user_id = self._get_user_id(event)
            user_storage_path = os.path.join(self.storage_path, f"user_{user_id}")
            os.makedirs(user_storage_path, exist_ok=True)
            
            if self.debug_mode:
                logger.info(f"[1.6.2] 处理私聊文件 - 用户: {user_id}, 存储路径: {user_storage_path}")
            
            # 检查用户文件数量限制并提醒删除
            removed_file = None
            if not self._check_file_limit(user_id, user_storage_path, self.max_files_per_user, "user"):
                record_file = os.path.join(user_storage_path, '.file_records.json')
                if os.path.exists(record_file):
                    with open(record_file, 'r', encoding='utf-8') as f:
                        try:
                            records = json.load(f)
                            if records:
                                removed_file = records[0].get('final_filename', '未知文件')
                        except:
                            pass
                
                if self.send_completion_message:
                    if self.send_completion_message:
                        msg = "❌ 文件存储数量已达上限!"
                        msg += "\n📥 检测到文件数量超限,正在自动删除最旧文件..." 
                        if removed_file:
                            msg += f"\n🗑️ 已自动删除最旧文件: {removed_file}"
                        msg += "\n✅ 文件删除完成,现在可以接收新文件了。"
                        await event.send(event.plain_result(msg))
            
            await self._process_file_download(event, file_component, user_storage_path, "user", user_id)
            
        except Exception as e:
            logger.error(f"[FileHandler-1.6.2] 处理私聊文件时出错: {e}")
            logger.exception(e)
    
    async def _handle_group_file_v159(self, event: AstrMessageEvent, file_component, group_id):
        """处理群聊文件"""
        try:
            group_storage_path = os.path.join(self.storage_path, f"group_{group_id}")
            os.makedirs(group_storage_path, exist_ok=True)
            
            if self.debug_mode:
                logger.info(f"[1.6.2] 处理群聊文件 - 群: {group_id}, 存储路径: {group_storage_path}")
            
            # 检查群文件数量限制并提醒删除
            removed_file = None
            if not self._check_file_limit(group_id, group_storage_path, self.max_files_per_group, "group"):
                record_file = os.path.join(group_storage_path, '.file_records.json')
                if os.path.exists(record_file):
                    with open(record_file, 'r', encoding='utf-8') as f:
                        try:
                            records = json.load(f)
                            if records:
                                removed_file = records[0].get('final_filename', '未知文件')
                        except:
                            pass
                
                if self.send_completion_message:
                    if self.send_completion_message:
                        msg = "❌ 群文件存储数量已达上限!"
                        msg += "\n📥 检测到群文件数量超限,正在自动删除最旧文件..." 
                        if removed_file:
                            msg += f"\n🗑️ 已自动删除最旧文件: {removed_file}"
                        msg += "\n✅ 文件删除完成,现在可以接收新文件了。"
                        await event.send(event.plain_result(msg))
            
            await self._process_file_download(event, file_component, group_storage_path, "group", group_id)
            
        except Exception as e:
            logger.error(f"[FileHandler-1.6.2] 处理群聊文件时出错: {e}")
            logger.exception(e)
    
    async def _process_file_download(self, event: AstrMessageEvent, file_component, storage_path, file_type, identifier):
        """处理文件下载的通用方法"""
        try:
            file_attrs = self._extract_file_attributes(file_component)
            original_name = self._extract_filename(file_attrs)
            file_url = self._extract_file_url(file_attrs)
            file_id = file_attrs.get('id') or file_attrs.get('file_id')
            file_size = file_attrs.get('size') or file_attrs.get('file_size', 0)
            
            if self.debug_mode:
                logger.info(f"[1.6.2] {file_type}文件信息 - 名称: '{original_name}', 大小: {file_size} bytes")
                logger.info(f"[1.6.2] 文件URL: {file_url}")
                logger.info(f"[1.6.2] 文件ID: {file_id}")
            
            if self.max_file_size_mb > 0:
                max_size_bytes = self.max_file_size_mb * 1024 * 1024
                if file_size <= 0 and file_url:
                    if 'large' in file_url.lower() or 'video' in file_url.lower():
                        file_size = max_size_bytes + 1
                
                if file_size > max_size_bytes:
                    size_mb = file_size / (1024 * 1024) if file_size > 0 else "未知"
                    max_mb = self.max_file_size_mb
                    if self.send_completion_message:
                        await event.send(event.plain_result(
                            f"❌ 文件过大无法下载!\n"
                            f"文件大小: {size_mb}MB\n"
                            f"大小限制: {max_mb}MB"
                        ))
                    return
            
            temp_filename = f"temp_file_{int(time.time())}"
            temp_filepath = os.path.join(storage_path, temp_filename)
            
            if file_url:
                download_success = await self._download_to_temp(file_url, temp_filepath)
                if download_success:
                    detected_type = self._detect_file_type_detailed(temp_filepath)
                    final_filename = self._smart_filename_handling(original_name, detected_type, temp_filepath)
                    final_filepath = os.path.join(storage_path, final_filename)
                    final_filepath = self._ensure_unique_filename(final_filepath)
                    
                    os.rename(temp_filepath, final_filepath)
                    if self.debug_mode:
                        logger.info(f"[1.6.2] 文件已保存: {final_filepath}")
                    
                    record_info = {
                        'identifier': identifier,
                        'type': file_type,
                        'original_name': original_name,
                        'final_filename': final_filename,
                        'file_path': final_filepath,
                        'file_url': file_url,
                        'file_id': file_id,
                        'file_size': os.path.getsize(final_filepath),
                        'file_type': detected_type,
                        'receive_time': time.time(),
                        'sender': event.get_sender_name() if hasattr(event, 'get_sender_name') else 'unknown',
                        'platform': event.get_platform_name() if hasattr(event, 'get_platform_name') else 'unknown',
                        'download_status': 'success'
                    }
                    
                    record_file = os.path.join(storage_path, '.file_records.json')
                    self._save_record(record_file, record_info)
                    
                    if self.send_completion_message:
                        actual_size = os.path.getsize(final_filepath)
                        await self._send_completion_message(event, final_filename, final_filepath, actual_size, detected_type, original_name, file_type)
                        
                else:
                    if os.path.exists(temp_filepath):
                        os.remove(temp_filepath)
                    
                    record_info = {
                        'identifier': identifier,
                        'type': file_type,
                        'original_name': original_name,
                        'file_url': file_url,
                        'file_id': file_id,
                        'file_size': file_size,
                        'receive_time': time.time(),
                        'sender': event.get_sender_name() if hasattr(event, 'get_sender_name') else 'unknown',
                        'platform': event.get_platform_name() if hasattr(event, 'get_platform_name') else 'unknown',
                        'download_status': 'failed'
                    }
                    
                    record_file = os.path.join(storage_path, '.file_records.json')
                    self._save_record(record_file, record_info)
                    
                    if self.send_completion_message:
                        await event.send(event.plain_result(f"❌ 文件 {original_name} 下载失败!"))
            else:
                record_info = {
                    'identifier': identifier,
                    'type': file_type,
                    'original_name': original_name,
                    'file_url': file_url,
                    'file_id': file_id,
                    'file_size': file_size,
                    'receive_time': time.time(),
                    'sender': event.get_sender_name() if hasattr(event, 'get_sender_name') else 'unknown',
                    'platform': event.get_platform_name() if hasattr(event, 'get_platform_name') else 'unknown',
                    'download_status': 'no_url'
                }
                
                record_file = os.path.join(storage_path, '.file_records.json')
                self._save_record(record_file, record_info)
            
        except Exception as e:
            logger.error(f"[FileHandler-1.6.2] 处理文件下载时出错: {e}")
            logger.exception(e)
    
    # ==================== 私聊指令 ====================
    @filter.command("查看文件", alias={'/fileinfo'})
    async def view_files(self, event: AstrMessageEvent):
        """查看私聊文件"""
        user_id = self._get_user_id(event)
        user_storage_path = os.path.join(self.storage_path, f"user_{user_id}")
        
        record_file = os.path.join(user_storage_path, '.file_records.json')
        if not os.path.exists(record_file):
            await event.send(event.plain_result("📁 暂无文件记录"))
            return
        
        try:
            with open(record_file, 'r', encoding='utf-8') as f:
                records = json.load(f)
                success_records = [r for r in records if r.get('download_status') == 'success']
        except:
            await event.send(event.plain_result("❌ 读取记录文件出错"))
            return
        
        if not success_records:
            await event.send(event.plain_result("📁 暂无文件记录"))
            return
        
        success_records.sort(key=lambda x: x.get('receive_time', 0), reverse=True)
        
        msg_lines = [f"📄 您的私聊文件 (共{len(success_records)}个文件):"]
        msg_lines.append("序号 | 文件名 | 大小 | 类型 | 时间")
        msg_lines.append("-" * 50)
        
        for i, record in enumerate(success_records[:10], 1):
            filename = record.get('final_filename', 'unknown')[:20]
            size = self._format_file_size(record.get('file_size', 0))
            filetype = record.get('file_type', 'unknown')
            time_str = time.strftime('%m-%d %H:%M', time.localtime(record.get('receive_time', 0)))
            
            msg_lines.append(f"{i}. {filename} | {size} | {filetype} | {time_str}")
        
        if len(success_records) > 10:
            msg_lines.append(f"... 还有{len(success_records) - 10}个文件")
        
        msg_lines.append("\n指令: /发送文件 <序号/文件名>  /删除文件 <序号/文件名>")
        
        await event.send(event.plain_result('\n'.join(msg_lines)))
    
    @filter.command("发送文件")
    async def send_file(self, event: AstrMessageEvent, file_identifier: str = ""):
        """发送私聊文件"""
        if not file_identifier:
            await event.send(event.plain_result("❌ 请指定要发送的文件\n用法: /发送文件 <序号> 或 /发送文件 <文件名>"))
            return
        
        user_id = self._get_user_id(event)
        user_storage_path = os.path.join(self.storage_path, f"user_{user_id}")
        
        record_file = os.path.join(user_storage_path, '.file_records.json')
        if not os.path.exists(record_file):
            await event.send(event.plain_result("❌ 暂无文件记录"))
            return
        
        try:
            with open(record_file, 'r', encoding='utf-8') as f:
                records = json.load(f)
                success_records = [r for r in records if r.get('download_status') == 'success']
        except:
            await event.send(event.plain_result("❌ 读取记录文件出错"))
            return
        
        if not success_records:
            await event.send(event.plain_result("❌ 暂无文件记录"))
            return
        
        success_records.sort(key=lambda x: x.get('receive_time', 0), reverse=True)
        
        target_record = None
        
        if file_identifier.isdigit():
            index = int(file_identifier) - 1
            if 0 <= index < len(success_records):
                target_record = success_records[index]
            else:
                await event.send(event.plain_result(f"❌ 序号超出范围 (1-{len(success_records)})"))
                return
        else:
            for record in success_records:
                if file_identifier in record.get('final_filename', ''):
                    target_record = record
                    break
            
            if not target_record:
                for record in success_records:
                    final_name = record.get('final_filename', '').lower()
                    orig_name = record.get('original_name', '').lower()
                    if file_identifier.lower() in final_name or file_identifier.lower() in orig_name:
                        target_record = record
                        break
            
            if not target_record:
                await event.send(event.plain_result(f"❌ 未找到文件: {file_identifier}"))
                return
        
        file_path = target_record.get('file_path', '')
        if not file_path or not os.path.exists(file_path):
            await event.send(event.plain_result("❌ 文件不存在或已被删除"))
            return
        
        filename = target_record.get('final_filename', 'file')
        
        try:
            import astrbot.api.message_components as Comp
            chain = [
                Comp.Plain(f"📁 文件: {filename}\n"),
                Comp.File(file=file_path, name=filename)
            ]
            await event.send(event.chain_result(chain))
            if self.debug_mode:
                logger.info(f"[1.6.2] 已发送文件: {filename}")
            
        except ImportError:
            if hasattr(event, 'file_result'):
                await event.send(event.file_result(file_path, filename))
            else:
                await event.send(event.plain_result(f"📁 文件: {filename}\n路径: {file_path}"))
    
    @filter.command("删除文件")
    async def delete_file(self, event: AstrMessageEvent, file_identifier: str = ""):
        """删除私聊文件"""
        if not file_identifier:
            await event.send(event.plain_result("❌ 请指定要删除的文件\n用法: /删除文件 <序号> 或 /删除文件 <文件名>"))
            return
        
        user_id = self._get_user_id(event)
        user_storage_path = os.path.join(self.storage_path, f"user_{user_id}")
        
        record_file = os.path.join(user_storage_path, '.file_records.json')
        if not os.path.exists(record_file):
            await event.send(event.plain_result("❌ 暂无文件记录"))
            return
        
        try:
            with open(record_file, 'r', encoding='utf-8') as f:
                records = json.load(f)
        except:
            await event.send(event.plain_result("❌ 读取记录文件出错"))
            return
        
        if not records:
            await event.send(event.plain_result("❌ 暂无文件记录"))
            return
        
        records.sort(key=lambda x: x.get('receive_time', 0), reverse=True)
        
        target_record = None
        target_index = -1
        
        if file_identifier.isdigit():
            index = int(file_identifier) - 1
            if 0 <= index < len(records):
                target_record = records[index]
                target_index = index
            else:
                await event.send(event.plain_result(f"❌ 序号超出范围 (1-{len(records)})"))
                return
        else:
            for i, record in enumerate(records):
                if file_identifier in record.get('final_filename', ''):
                    target_record = record
                    target_index = i
                    break
            
            if not target_record:
                for i, record in enumerate(records):
                    final_name = record.get('final_filename', '').lower()
                    orig_name = record.get('original_name', '').lower()
                    if file_identifier.lower() in final_name or file_identifier.lower() in orig_name:
                        target_record = record
                        target_index = i
                        break
            
            if not target_record:
                await event.send(event.plain_result(f"❌ 未找到文件: {file_identifier}"))
                return
        
        file_path = target_record.get('file_path', '')
        filename = target_record.get('final_filename', 'unknown')
        
        if file_path and os.path.exists(file_path):
            try:
                os.remove(file_path)
                if self.debug_mode:
                    logger.info(f"[1.6.2] 已删除文件: {file_path}")
            except Exception as e:
                logger.error(f"[1.6.2] 删除文件时出错: {e}")
                await event.send(event.plain_result(f"❌ 删除文件失败: {filename}"))
                return
        
        records.pop(target_index)
        with open(record_file, 'w', encoding='utf-8') as f:
            json.dump(records, f, ensure_ascii=False, indent=2)
        
        await event.send(event.plain_result(f"✅ 文件删除成功!\n文件名: {filename}"))
        if self.debug_mode:
            logger.info(f"[1.6.2] 已删除文件记录: {filename}")
    
    @filter.command("重置文件")
    async def reset_files(self, event: AstrMessageEvent):
        """重置私聊文件"""
        user_id = self._get_user_id(event)
        user_storage_path = os.path.join(self.storage_path, f"user_{user_id}")
        
        if not os.path.exists(user_storage_path):
            await event.send(event.plain_result("📁 暂无文件记录"))
            return
        
        # 删除所有文件
        deleted_count = 0
        if os.path.exists(user_storage_path):
            for file in os.listdir(user_storage_path):
                file_path = os.path.join(user_storage_path, file)
                if os.path.isfile(file_path) and not file.startswith('.'):
                    try:
                        os.remove(file_path)
                        deleted_count += 1
                        if self.debug_mode:
                            logger.info(f"[1.6.2] 已删除文件: {file_path}")
                    except Exception as e:
                        logger.error(f"[1.6.2] 删除文件时出错: {e}")
        
        # 删除记录文件
        record_file = os.path.join(user_storage_path, '.file_records.json')
        if os.path.exists(record_file):
            try:
                os.remove(record_file)
                if self.debug_mode:
                    logger.info(f"[1.6.2] 已删除记录文件: {record_file}")
            except Exception as e:
                logger.error(f"[1.6.2] 删除记录文件时出错: {e}")
        
        await event.send(event.plain_result(f"✅ 私聊文件重置完成!\n共删除 {deleted_count} 个文件"))
        if self.debug_mode:
            logger.info(f"[1.6.2] 用户 {user_id} 的私聊文件已重置")
    
    # ==================== 群聊指令 ====================
    @filter.command("查看群文件")
    async def view_group_files(self, event: AstrMessageEvent):
        """查看群文件 - 仅群聊可用"""
        if not hasattr(event.message_obj, 'group_id') or not event.message_obj.group_id:
            await event.send(event.plain_result("❌ 此指令只能在群聊中使用"))
            return
        
        group_id = str(event.message_obj.group_id)
        group_storage_path = os.path.join(self.storage_path, f"group_{group_id}")
        
        record_file = os.path.join(group_storage_path, '.file_records.json')
        if not os.path.exists(record_file):
            await event.send(event.plain_result("📁 暂无群文件记录"))
            return
        
        try:
            with open(record_file, 'r', encoding='utf-8') as f:
                records = json.load(f)
                success_records = [r for r in records if r.get('download_status') == 'success']
        except:
            await event.send(event.plain_result("❌ 读取记录文件出错"))
            return
        
        if not success_records:
            await event.send(event.plain_result("📁 暂无群文件记录"))
            return
        
        success_records.sort(key=lambda x: x.get('receive_time', 0), reverse=True)
        
        msg_lines = [f"📄 群 {group_id} 的文件 (共{len(success_records)}个文件):"]
        msg_lines.append("序号 | 文件名 | 大小 | 类型 | 时间")
        msg_lines.append("-" * 50)
        
        for i, record in enumerate(success_records[:10], 1):
            filename = record.get('final_filename', 'unknown')[:20]
            size = self._format_file_size(record.get('file_size', 0))
            filetype = record.get('file_type', 'unknown')
            time_str = time.strftime('%m-%d %H:%M', time.localtime(record.get('receive_time', 0)))
            
            msg_lines.append(f"{i}. {filename} | {size} | {filetype} | {time_str}")
        
        if len(success_records) > 10:
            msg_lines.append(f"... 还有{len(success_records) - 10}个文件")
        
        msg_lines.append("\n指令: /发送群文件 <序号/文件名>  /删除群文件 <序号/文件名>")
        
        await event.send(event.plain_result('\n'.join(msg_lines)))
    
    @filter.command("发送群文件")
    async def send_group_file(self, event: AstrMessageEvent, file_identifier: str = ""):
        """发送群文件 - 仅群聊可用"""
        if not file_identifier:
            await event.send(event.plain_result("❌ 请指定要发送的文件\n用法: /发送群文件 <序号> 或 /发送群文件 <文件名>"))
            return
        
        if not hasattr(event.message_obj, 'group_id') or not event.message_obj.group_id:
            await event.send(event.plain_result("❌ 此指令只能在群聊中使用"))
            return
        
        group_id = str(event.message_obj.group_id)
        group_storage_path = os.path.join(self.storage_path, f"group_{group_id}")
        
        record_file = os.path.join(group_storage_path, '.file_records.json')
        if not os.path.exists(record_file):
            await event.send(event.plain_result("❌ 暂无群文件记录"))
            return
        
        try:
            with open(record_file, 'r', encoding='utf-8') as f:
                records = json.load(f)
                success_records = [r for r in records if r.get('download_status') == 'success']
        except:
            await event.send(event.plain_result("❌ 读取记录文件出错"))
            return
        
        if not success_records:
            await event.send(event.plain_result("❌ 暂无群文件记录"))
            return
        
        success_records.sort(key=lambda x: x.get('receive_time', 0), reverse=True)
        
        target_record = None
        
        if file_identifier.isdigit():
            index = int(file_identifier) - 1
            if 0 <= index < len(success_records):
                target_record = success_records[index]
            else:
                await event.send(event.plain_result(f"❌ 序号超出范围 (1-{len(success_records)})"))
                return
        else:
            for record in success_records:
                if file_identifier in record.get('final_filename', ''):
                    target_record = record
                    break
            
            if not target_record:
                for record in success_records:
                    final_name = record.get('final_filename', '').lower()
                    orig_name = record.get('original_name', '').lower()
                    if file_identifier.lower() in final_name or file_identifier.lower() in orig_name:
                        target_record = record
                        break
            
            if not target_record:
                await event.send(event.plain_result(f"❌ 未找到文件: {file_identifier}"))
                return
        
        file_path = target_record.get('file_path', '')
        if not file_path or not os.path.exists(file_path):
            await event.send(event.plain_result("❌ 文件不存在或已被删除"))
            return
        
        filename = target_record.get('final_filename', 'file')
        
        try:
            import astrbot.api.message_components as Comp
            chain = [
                Comp.Plain(f"📁 文件: {filename}\n"),
                Comp.File(file=file_path, name=filename)
            ]
            await event.send(event.chain_result(chain))
            if self.debug_mode:
                logger.info(f"[1.6.2] 已发送群文件: {filename}")
            
        except ImportError:
            if hasattr(event, 'file_result'):
                await event.send(event.file_result(file_path, filename))
            else:
                await event.send(event.plain_result(f"📁 文件: {filename}\n路径: {file_path}"))
    
    @filter.command("删除群文件")
    async def delete_group_file(self, event: AstrMessageEvent, file_identifier: str = ""):
        """删除群文件 - 仅群聊可用"""
        if not file_identifier:
            await event.send(event.plain_result("❌ 请指定要删除的文件\n用法: /删除群文件 <序号> 或 /删除群文件 <文件名>"))
            return
        
        if not hasattr(event.message_obj, 'group_id') or not event.message_obj.group_id:
            await event.send(event.plain_result("❌ 此指令只能在群聊中使用"))
            return
        
        group_id = str(event.message_obj.group_id)
        group_storage_path = os.path.join(self.storage_path, f"group_{group_id}")
        
        record_file = os.path.join(group_storage_path, '.file_records.json')
        if not os.path.exists(record_file):
            await event.send(event.plain_result("❌ 暂无群文件记录"))
            return
        
        try:
            with open(record_file, 'r', encoding='utf-8') as f:
                records = json.load(f)
        except:
            await event.send(event.plain_result("❌ 读取记录文件出错"))
            return
        
        if not records:
            await event.send(event.plain_result("❌ 暂无群文件记录"))
            return
        
        records.sort(key=lambda x: x.get('receive_time', 0), reverse=True)
        
        target_record = None
        target_index = -1
        
        if file_identifier.isdigit():
            index = int(file_identifier) - 1
            if 0 <= index < len(records):
                target_record = records[index]
                target_index = index
            else:
                await event.send(event.plain_result(f"❌ 序号超出范围 (1-{len(records)})"))
                return
        else:
            for i, record in enumerate(records):
                if file_identifier in record.get('final_filename', ''):
                    target_record = record
                    target_index = i
                    break
            
            if not target_record:
                for i, record in enumerate(records):
                    final_name = record.get('final_filename', '').lower()
                    orig_name = record.get('original_name', '').lower()
                    if file_identifier.lower() in final_name or file_identifier.lower() in orig_name:
                        target_record = record
                        target_index = i
                        break
            
            if not target_record:
                await event.send(event.plain_result(f"❌ 未找到文件: {file_identifier}"))
                return
        
        file_path = target_record.get('file_path', '')
        filename = target_record.get('final_filename', 'unknown')
        
        if file_path and os.path.exists(file_path):
            try:
                os.remove(file_path)
                if self.debug_mode:
                    logger.info(f"[1.6.2] 已删除群文件: {file_path}")
            except Exception as e:
                logger.error(f"[1.6.2] 删除群文件时出错: {e}")
                await event.send(event.plain_result(f"❌ 删除群文件失败: {filename}"))
                return
        
        records.pop(target_index)
        with open(record_file, 'w', encoding='utf-8') as f:
            json.dump(records, f, ensure_ascii=False, indent=2)
        
        await event.send(event.plain_result(f"✅ 群文件删除成功!\n文件名: {filename}"))
        if self.debug_mode:
            logger.info(f"[1.6.2] 已删除群文件记录: {filename}")
    
    @filter.command("重置群文件")
    async def reset_group_files(self, event: AstrMessageEvent):
        """重置群文件 - 仅群聊可用"""
        if not hasattr(event.message_obj, 'group_id') or not event.message_obj.group_id:
            await event.send(event.plain_result("❌ 此指令只能在群聊中使用"))
            return
        
        group_id = str(event.message_obj.group_id)
        group_storage_path = os.path.join(self.storage_path, f"group_{group_id}")
        
        if not os.path.exists(group_storage_path):
            await event.send(event.plain_result("📁 暂无群文件记录"))
            return
        
        # 删除所有文件
        deleted_count = 0
        if os.path.exists(group_storage_path):
            for file in os.listdir(group_storage_path):
                file_path = os.path.join(group_storage_path, file)
                if os.path.isfile(file_path) and not file.startswith('.'):
                    try:
                        os.remove(file_path)
                        deleted_count += 1
                        if self.debug_mode:
                            logger.info(f"[1.6.2] 已删除群文件: {file_path}")
                    except Exception as e:
                        logger.error(f"[1.6.2] 删除群文件时出错: {e}")
        
        # 删除记录文件
        record_file = os.path.join(group_storage_path, '.file_records.json')
        if os.path.exists(record_file):
            try:
                os.remove(record_file)
                if self.debug_mode:
                    logger.info(f"[1.6.2] 已删除群记录文件: {record_file}")
            except Exception as e:
                logger.error(f"[1.6.2] 删除群记录文件时出错: {e}")
        
        await event.send(event.plain_result(f"✅ 群 {group_id} 文件重置完成!\n共删除 {deleted_count} 个文件"))
        if self.debug_mode:
            logger.info(f"[1.6.2] 群 {group_id} 的文件已重置")
    
    @filter.command("接收群文件")
    async def receive_group_file(self, event: AstrMessageEvent):
        """接收群文件 - 改进版逻辑"""
        if not hasattr(event.message_obj, 'group_id') or not event.message_obj.group_id:
            await event.send(event.plain_result("❌ 此指令只能在群聊中使用"))
            return
        
        if self.auto_receive_group_files:
            await event.send(event.plain_result("✅ 自动接收群文件已开启,无需手动接收"))
            return
        
        group_id = str(event.message_obj.group_id)
        user_id = self._get_user_id(event)
        
        # 设置等待接收状态
        expire_time = time.time() + self.group_file_receive_timeout
        self.pending_group_receives[group_id][user_id] = expire_time
        
        timeout_msg = f"{self.group_file_receive_timeout}"
        await event.send(event.plain_result(
            f"💡 请在 {timeout_msg} 秒内发送要接收的文件\n"
            f"支持直接发送或引用文件消息\n"
            f"超时将自动取消接收"
        ))
        
        if self.debug_mode:
            logger.info(f"[1.6.2] 群 {group_id} 用户 {user_id} 开始等待文件接收,超时时间: {timeout_msg}秒")
    
    def _get_user_id(self, event: AstrMessageEvent):
        """获取用户ID"""
        try:
            if hasattr(event, 'message_obj') and event.message_obj:
                message_obj = event.message_obj
                if hasattr(message_obj, 'sender') and message_obj.sender:
                    user_id = getattr(message_obj.sender, 'user_id', None)
                    if user_id:
                        return str(user_id)
            
            sender_name = event.get_sender_name() if hasattr(event, 'get_sender_name') else 'unknown'
            platform = event.get_platform_name() if hasattr(event, 'get_platform_name') else 'unknown'
            return f"{sender_name}_{platform}"
            
        except Exception as e:
            logger.error(f"[1.6.2] 获取用户ID时出错: {e}")
            return "unknown_user"
    

    def _check_file_limit(self, entity_id, storage_path, max_files, entity_type="user"):
        """通用文件数量限制检查"""
        try:
            record_file = os.path.join(storage_path, '.file_records.json')
            if not os.path.exists(record_file):
                return True

            with open(record_file, 'r', encoding='utf-8') as f:
                try:
                    records = json.load(f)
                    success_records = [r for r in records if r.get('download_status') == 'success']

                    if len(success_records) >= max_files:
                        entity_desc = "用户" if entity_type == "user" else "群"
                        logger.warning(f"[1.6.2] 检测到{entity_desc}文件数量已达上限({max_files})")
                        logger.info(f"[1.6.2] 准备删除最旧文件以腾出空间")
                        logger.warning(f"[1.6.2] {entity_desc}文件数量已达上限({max_files}),将自动删除最旧文件")
                        self._remove_oldest_file(success_records, storage_path, record_file)
                        logger.info(f"[1.6.2] 已自动删除最旧文件,为新文件腾出空间")
                        logger.info(f"[1.6.2] 文件删除完成,允许接收新文件")
                        return True
                    else:
                        return True

                except:
                    return True

        except Exception as e:
            entity_desc = "用户" if entity_type == "user" else "群"
            logger.error(f"[1.6.2] 检查{entity_desc}文件限制时出错: {e}")
            return True
            # [v1.6.2] 删除旧文件后继续处理新文件\n
    def _remove_oldest_file(self, records, storage_path, record_file):
        """删除最旧的文件"""
        try:
            records.sort(key=lambda x: x.get('receive_time', 0))
            oldest_record = records[0]
            
            file_path = oldest_record.get('file_path', '')
            if file_path and os.path.exists(file_path):
                try:
                    os.remove(file_path)
                    if self.debug_mode:
                        logger.info(f"[1.6.2] 已删除最旧文件: {file_path}")
                except Exception as e:
                    logger.error(f"[1.6.2] 删除文件时出错: {e}")
            
            remaining_records = records[1:]
            with open(record_file, 'w', encoding='utf-8') as f:
                json.dump(remaining_records, f, ensure_ascii=False, indent=2)
                
        except Exception as e:
            logger.error(f"[1.6.2] 删除最旧文件时出错: {e}")
    
    def _smart_filename_handling(self, original_name, detected_type, file_path):
        """智能文件名处理"""
        try:
            if (original_name and 
                original_name not in ['unknown_file', 'qqdownloadftnv5'] and
                len(original_name) > 5 and
                '.' in original_name):
                
                original_ext = os.path.splitext(original_name)[1].lower()
                detected_ext = detected_type.lower()
                
                if (original_ext == detected_ext or 
                    (original_ext in ['.docx', '.doc'] and detected_ext in ['.docx', '.doc']) or
                    (original_ext in ['.xlsx', '.xls'] and detected_ext in ['.xlsx', '.xls']) or
                    (original_ext in ['.pptx', '.ppt'] and detected_ext in ['.pptx', '.ppt'])):
                    
                    if self.debug_mode:
                        logger.info(f"[1.6.2] 使用有效的原始文件名: {original_name}")
                    return self._sanitize_filename(original_name)
            
            name_without_ext = os.path.splitext(original_name)[0]
            if name_without_ext and name_without_ext not in ['unknown_file', 'qqdownloadftnv5']:
                final_name = f"{name_without_ext}{detected_type}"
            else:
                timestamp = int(time.time())
                final_name = f"file_{timestamp}{detected_type}"
            
            return self._sanitize_filename(final_name)
            
        except Exception as e:
            logger.error(f"[1.6.2] 智能文件名处理出错: {e}")
            timestamp = int(time.time())
            return f"file_{timestamp}{detected_type}"
    
    async def _send_completion_message(self, event: AstrMessageEvent, filename, filepath, filesize, filetype, original_name, file_type):
        """发送完成消息"""
        try:
            size_str = self._format_file_size(filesize)
            
            if original_name in ['unknown_file', 'qqdownloadftnv5'] or not original_name:
                completion_msg = f"""✅ {'群' if file_type == 'group' else '私聊'}文件接收成功!
文件名: {filename}
大小: {size_str}
类型: {filetype}
路径: {filepath}

💡 提示: 由于环境限制,原始文件名无法获取
系统已为您生成新的文件名: {filename}"""
            else:
                completion_msg = f"""✅ {'群' if file_type == 'group' else '私聊'}文件接收成功!
原始名: {original_name}
保存为: {filename}
大小: {size_str}
类型: {filetype}
路径: {filepath}"""
            
            await event.send(event.plain_result(completion_msg))
            if self.debug_mode:
                logger.info(f"[1.6.2] 已发送完成消息: {filename}")
            # 自动读取文本文件内容功能
            if self.auto_read_content:
                # 检查文件大小限制
                try:
                    file_size = os.path.getsize(filepath)
                    max_size = self.max_auto_read_size

                    if file_size <= max_size:
                        # 检查是否为文本文件
                        if self._is_text_file_safe(filepath):
                            # 读取文件内容
                            content = self._read_text_file_safely(filepath)
                            if content:
                                logger.info(f"[AutoRead] 自动读取文本文件内容: {filename}")
                                
                                # 核心功能:将文件内容作为用户消息处理,触发AI自然回复
                                try:
                                    clean_content = content.strip()
                                    if len(clean_content) > self.max_auto_read_size:
                                        clean_content = clean_content[:self.max_auto_read_size] + "\n[内容已截断,原文过长]"
                                    
                                    await self._handle_file_as_user_message(event, clean_content, filename)
                                    logger.info(f"[AutoRead-AI] 已提交AI处理文件内容")
                                except Exception as ai_error:
                                    logger.error(f"[AutoRead-AI] AI处理失败: {ai_error}")
                                    # AI处理失败时的降级处理
                                    try:
                                        await self._send_reply(event, f"📄 文件内容:\n{content[:500]}...")
                                    except:
                                        try:
                                            from astrbot.api.event import MessageChain
                                            message_chain = MessageChain().message(f"📄 文件已读取并提交AI分析")
                                            await self.context.send_message(event.unified_msg_origin, message_chain)
                                        except:
                                            pass
                            else:
                                logger.info(f"[AutoRead] 文件内容为空或读取失败")
                    else:
                        logger.info(f"[AutoRead] 文件过大,跳过自动读取: {file_size} bytes > {max_size} bytes")
                except Exception as size_error:
                    logger.error(f"[AutoRead] 检查文件时出错: {size_error}")
        except Exception as e:
            logger.error(f"[1.6.2] 发送完成消息出错: {e}")
    
    def _format_file_size(self, size_bytes):
        """格式化文件大小"""
        if size_bytes < 1024:
            return f"{size_bytes} B"
        elif size_bytes < 1024 * 1024:
            return f"{size_bytes / 1024:.1f} KB"
        elif size_bytes < 1024 * 1024 * 1024:
            return f"{size_bytes / (1024 * 1024):.1f} MB"
        else:
            return f"{size_bytes / (1024 * 1024 * 1024):.1f} GB"
    
    def _detect_file_type_detailed(self, filepath):
        """增强的文件类型检测 - 修复PPTX识别问题和文本文件识别问题
        
        支持五层检测机制:
        1. filetype库检测
        2. 文本文件检测
        3. 文件头特征分析
        4. 二进制文件判断
        5. 默认类型返回
        """
        import os
        
        # 检查文件是否存在
        if not os.path.exists(filepath):
            return ".bin"
        
        # [v1.6.2] 第一层检测:使用filetype库(如果可用)
        try:
            import filetype
            kind = filetype.guess(filepath)
            if kind is not None:
                detected_ext = f".{kind.extension}"
                if self.debug_mode:
                    logger.info(f"[1.6.2] filetype库检测结果: {kind.mime} -> {detected_ext}")
                # 特别处理Office文件以确保准确性
                if detected_ext in ['.docx', '.xlsx', '.pptx', '.doc', '.xls', '.ppt']:
                    return detected_ext
                # 对于已知文本类型,直接返回
                text_types = ['.txt', '.py', '.c', '.cpp', '.h', '.java', '.js', '.html', '.css', '.xml', '.json', '.yaml', '.yml', '.md', '.csv', '.log']
                if detected_ext in text_types:
                    return detected_ext
        except ImportError:
            if self.debug_mode:
                logger.debug("[1.6.2] filetype库未安装,跳过第一层检测")
        except Exception as e:
            if self.debug_mode:
                logger.warning(f"[1.6.2] filetype库检测异常: {e}")
        
        # [v1.6.2] 第二层检测:文本文件检测
        try:
            is_text, encoding = self._is_text_file_safe(filepath)
            if is_text:
                if self.debug_mode:
                    logger.info(f"[1.6.2] 检测到文本文件,编码: {encoding}")
                return ".txt"
        except Exception as e:
            if self.debug_mode:
                logger.warning(f"[1.6.2] 文本文件检测异常: {e}")
        
        # [v1.6.2] 第三层检测:文件头特征分析
        try:
            with open(filepath, 'rb') as f:
                header = f.read(1024)  # 读取前1024字节
            
            # 检查常见的文件头特征
            if header.startswith(b'\x89PNG\r\n\x1a\n'):
                return ".png"
            elif header.startswith(b'\xff\xd8\xff'):
                return ".jpg"
            elif header.startswith(b'GIF87a') or header.startswith(b'GIF89a'):
                return ".gif"
            elif header.startswith(b'%PDF'):
                return ".pdf"
            elif header.startswith(b'PK'):
                # ZIP文件,可能是Office文档
                return ".zip"
            elif header.startswith(b'\x1f\x8b'):
                return ".gz"
            elif header.startswith(b'Rar!'):
                return ".rar"
        except Exception as e:
            if self.debug_mode:
                logger.warning(f"[1.6.2] 文件头检测异常: {e}")
        
        # [v1.6.2] 第四层检测:二进制文件判断
        try:
            with open(filepath, 'rb') as f:
                sample = f.read(1024)
            
            # 检查是否包含大量不可打印字符
            if sample:
                non_printable = sum(1 for byte in sample if byte < 32 and byte not in [9, 10, 13])
                printable_ratio = 1 - (non_printable / len(sample))
                
                if printable_ratio < 0.7:  # 如果可打印字符少于70%,认为是二进制文件
                    if self.debug_mode:
                        logger.info(f"[1.6.2] 检测到二进制文件,可打印字符比例: {printable_ratio:.2f}")
                    return ".bin"
        except Exception as e:
            if self.debug_mode:
                logger.warning(f"[1.6.2] 二进制文件检测异常: {e}")
        
        # [v1.6.2] 第五层检测:默认返回策略
        # 如果前面都无法确定,优先返回.txt而不是.bin
        if self.debug_mode:
            logger.info("[1.6.2] 无法确定文件类型,返回默认.txt")
        return ".txt"

    def _extract_file_attributes(self, file_component):
        """提取文件属性"""
        attrs = {}
        try:
            attr_names = [attr for attr in dir(file_component) if not attr.startswith('_')]
            for attr in attr_names:
                try:
                    value = getattr(file_component, attr)
                    if isinstance(value, (str, int, float, bool, type(None))):
                        attrs[attr] = value
                except:
                    pass
        except Exception as e:
            logger.error(f"[1.6.2] 提取属性时出错: {e}")
        return attrs
    
    def _extract_filename(self, file_attrs):
        """提取文件名"""
        filename = (file_attrs.get('name') or 
                file_attrs.get('filename') or 
                file_attrs.get('file_name') or 
                'unknown_file')
        result = self._sanitize_filename(filename) if filename else 'unknown_file'
        if self.debug_mode:
            logger.info(f"[1.6.2] 提取文件名: '{filename}' -> '{result}'")
        return result
    
    def _extract_file_url(self, file_attrs):
        """提取文件URL"""
        url = (file_attrs.get('url') or 
            file_attrs.get('file_url') or 
            file_attrs.get('path') or 
            file_attrs.get('file_path'))
        if self.debug_mode and url:
            logger.info(f"[1.6.2] 提取文件URL: {url[:100]}...")  # 只显示前100字符
        return url
    
    async def _download_to_temp(self, url, temp_path):
        """下载到临时文件"""
        try:
            if self.debug_mode:
                logger.info(f"[1.6.2] 开始下载: {url[:100]}...")  # 只显示前100字符
            
            timeout = aiohttp.ClientTimeout(total=120)
            async with aiohttp.ClientSession(timeout=timeout) as session:
                async with session.get(url) as response:
                    if response.status == 200:
                        with open(temp_path, 'wb') as f:
                            async for chunk in response.content.iter_chunked(8192):
                                f.write(chunk)
                        if self.debug_mode:
                            logger.info(f"[1.6.2] 下载成功: {temp_path}")
                        return True
                    else:
                        if self.debug_mode:
                            logger.error(f"[1.6.2] 下载失败 HTTP {response.status}")
                        return False
                        
        except Exception as e:
            if self.debug_mode:
                logger.error(f"[1.6.2] 下载出错: {e}")
            return False
    
    async def _cleanup_task(self):
        """自动清理任务"""
        while True:
            try:
                if self.auto_cleanup_enabled:
                    await asyncio.sleep(3600)
                    self._cleanup_expired_files()
            except Exception as e:
                logger.error(f"[1.6.2] 清理任务出错: {e}")
                await asyncio.sleep(60)
    
    def _cleanup_expired_files(self):
        """清理过期文件"""
        try:
            if not os.path.exists(self.storage_path):
                return
                
            for item in os.listdir(self.storage_path):
                item_path = os.path.join(self.storage_path, item)
                if os.path.isdir(item_path):
                    record_file = os.path.join(item_path, '.file_records.json')
                    if not os.path.exists(record_file):
                        continue
                    
                    with open(record_file, 'r', encoding='utf-8') as f:
                        try:
                            records = json.load(f)
                        except:
                            records = []
                    
                    current_time = time.time()
                    expired_records = []
                    valid_records = []
                    
                    for record in records:
                        receive_time = record.get('receive_time', 0)
                        file_path = record.get('file_path', '')
                        
                        if current_time - receive_time > self.cleanup_days * 24 * 3600:
                            expired_records.append(record)
                            if file_path and os.path.exists(file_path):
                                try:
                                    os.remove(file_path)
                                    if self.debug_mode:
                                        logger.info(f"[1.6.2] 已删除过期文件: {file_path}")
                                except Exception as e:
                                    logger.error(f"[1.6.2] 删除文件出错: {e}")
                        else:
                            valid_records.append(record)
                    
                    with open(record_file, 'w', encoding='utf-8') as f:
                        json.dump(valid_records, f, ensure_ascii=False, indent=2)
                    
                    if expired_records and self.debug_mode:
                        logger.info(f"[1.6.2] 目录 {item} 清理了 {len(expired_records)} 个过期文件")
                        
        except Exception as e:
            logger.error(f"[1.6.2] 清理过期文件出错: {e}")
    
    def _ensure_unique_filename(self, filepath):
        """确保文件名唯一"""
        counter = 1
        name, ext = os.path.splitext(filepath)
        
        while os.path.exists(filepath):
            filepath = f"{name}_{counter}{ext}"
            counter += 1
            if counter > 1000:
                filepath = f"{name}_{int(time.time())}_{counter}{ext}"
                break
        
        if self.debug_mode and counter > 1:
            logger.info(f"[1.6.2] 文件名冲突,生成唯一文件名: {filepath}")
        
        return filepath
    
    def _sanitize_filename(self, filename):
        """清理文件名"""
        if not filename:
            return 'unnamed_file.bin'
        
        illegal_chars = '<>:"/\\|?*'
        for char in illegal_chars:
            filename = filename.replace(char, '_')
        
        filename = ''.join(char for char in filename if ord(char) >= 32)
        filename = re.sub(r'_+', '_', filename)
        filename = filename.strip('_. ')
        
        return filename if filename else 'unnamed_file.bin'
    
    async def _save_record(self, record_file, record_info):
        """保存记录"""
        try:
            records = []
            if os.path.exists(record_file):
                with open(record_file, 'r', encoding='utf-8') as f:
                    try:
                        records = json.load(f)
                    except:
                        records = []
            
            records.append(record_info)
            
            with open(record_file, 'w', encoding='utf-8') as f:
                json.dump(records, f, ensure_ascii=False, indent=2)
                
            if self.debug_mode:
                logger.info(f"[1.6.2] 记录已保存")
                
        except Exception as e:
            logger.error(f"[1.6.2] 保存记录出错: {e}")
    
    @filter.command("filestatus")
    async def file_status(self, event: AstrMessageEvent):
        """查看插件状态"""
        status_msg = f"""📁 文件处理器状态 (v1.6.2):
存储路径: {self.storage_path}
自动清理: {'✅ 启用' if self.auto_cleanup_enabled else '❌ 禁用'}
清理天数: {self.cleanup_days}天
完成消息: {'✅ 启用' if self.send_completion_message else '❌ 禁用'}
私聊文件限制: {self.max_files_per_user}个/用户
群聊文件限制: {self.max_files_per_group}个/群
文件大小限制: {self.max_file_size_mb}MB
群聊白名单: {'全部群' if not self.group_whitelist else self.group_whitelist}
自动接收群文件: {'✅ 启用' if self.auto_receive_group_files else '❌ 禁用'}
接收超时时间: {self.group_file_receive_timeout}秒
LLM工具支持: {'✅ 启用' if LLM_TOOL_SUPPORT else '❌ 禁用'}
调试模式: {'✅ 开启' if self.debug_mode else '❌ 关闭'}"""

    def _is_text_file(self, file_path: str) -> bool:
        """检查是否为文本文件"""
        text_extensions = {
            ".txt", ".py", ".c", ".cpp", ".h", ".java", ".js", ".html", 
            ".css", ".xml", ".json", ".yaml", ".yml", ".md", ".log", ".csv"
        }
        
        _, ext = os.path.splitext(file_path.lower())
        return ext in text_extensions

    def _is_text_file_safe(self, filepath):
        """安全地检测是否为文本文件"""
        import os
        
        # 检查文件是否存在
        if not os.path.exists(filepath):
            return False, None
        
        encodings = ['utf-8', 'gbk', 'gb2312', 'latin1']
        
        for encoding in encodings:
            try:
                with open(filepath, 'r', encoding=encoding) as f:
                    # 读取前几KB来检测
                    sample = f.read(4096)
                    # 检查是否包含过多的控制字符
                    if sample:  # 确保sample不为空
                        control_chars = sum(1 for c in sample if ord(c) < 32 and c not in '\t\n\r')
                        if control_chars / len(sample) > 0.3:
                            continue  # 控制字符过多,可能不是文本文件
                    return True, encoding
            except UnicodeDecodeError:
                continue
            except Exception:
                continue
        
        return False, None

        
        for encoding in encodings:
            try:
                with open(file_path, "r", encoding=encoding) as f:
                    content = f.read()
                    # 限制内容长度以避免过长消息
                    if len(content) > 2000:
                        content = content[:2000] + "\n[内容已截断,原文过长]"
                    return content
            except UnicodeDecodeError:
                continue
            except Exception as e:
                logger.error(f"[AutoRead] 读取文件时出错: {e}")
                return ""
        
        logger.warning(f"[AutoRead] 无法解码文件: {file_path}")
        return ""

    def _read_text_file_safely(self, file_path: str) -> str:
        """安全地读取文本文件内容"""
        encodings = ["utf-8", "gbk", "gb2312", "latin1"]
        
        for encoding in encodings:
            try:
                with open(file_path, "r", encoding=encoding) as f:
                    content = f.read()
                    # 限制内容长度以避免过长消息
                    if len(content) > self.max_auto_read_size:
                        content = content[:self.max_auto_read_size] + "\n[内容已截断,原文过长]"
                    return content
            except UnicodeDecodeError:
                continue
            except Exception as e:
                logger.error(f"[AutoRead] 读取文件时出错: {e}")
                return ""
        
        logger.warning(f"[AutoRead] 无法解码文件: {file_path}")
        return ""

AutoFileHandlerPlugin = PluginMain
