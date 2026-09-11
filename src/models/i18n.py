"""国际化管理器 —— 中英文切换。"""

from PyQt5.QtCore import QObject, pyqtSignal
from models.config import load_config, save_config


TRANSLATIONS = {
    "zh_CN": {
        "app_title": "智能评价系统",
        "app_subtitle": "基于AIGC的学术论文智能评价",

        "upload_hint": "将文件拖放到此处\n或点击上传\n\n上传后可点击左侧按钮，或直接在下方对话",
        "upload_btn": "上传文件",
        "file_ready": "文件已就绪",
        "file_loaded": "已加载",
        "file_loaded_hint": "✓ {filename}\n\n点击左侧功能按钮，或直接在下方输入提问",
        "select_pdf": "选择 PDF 文件",
        "pdf_filter": "PDF 文件 (*.pdf)",

        "new_task": "新任务",
        "history": "历史记录",

        "basic": "1. Basic Evaluation",
        "advanced": "2. Advanced Evaluation",
        "summary": "3. Evaluation Summary",

        "eval_request": "请对当前论文执行：{name}",
        "scoring": "论文评分",
        "content_eval": "内容评价",
        "ensemble": "集成学习",
        "rag": "检索增强",
        "reflexion": "反思强化",
        "role_aware": "角色推理",
        "adversarial": "批判对抗",
        "innovation": "创新比较",
        "comprehensive": "综合评价",

        "chatbot": "IES Outputs",
        "input_placeholder": "输入消息，或将 PDF 拖入对话框（已上传文件时，可点左侧按钮也可直接对话）",
        "placeholder_title": "智能评价系统",
        "placeholder_desc": (
            "\n一个结合AIGC技术与智能评价理论的评估系统。\n"
            "可以自动分析、评价，并提供建议以提高\n"
            "评价的准确性、效率和客观性。"
        ),

        "file_load_success": "文件加载成功",
        "file_load_fail": "文件加载失败",
        "evaluating": "正在评价中...",
        "eval_complete": "评价完成",
        "eval_error": "评价出错",
        "stopping": "正在停止...",
        "stopped": "已停止",
        "eval_stopped_msg": "\n\n---\n**[ 评价已被用户停止 ]**",
        "upload_first": "请先上传 PDF 文件",
        "eval_running": "评价任务正在运行中",
        "abort_eval_confirm": "当前有正在进行的评价任务，是否中止并切换？",
        "hint": "提示",
        "stop_eval": "停止评价",

        "settings": "设置",
        "settings_subtitle": "个性化您的 IES 体验",
        "appearance": "外观",
        "theme": "主题",
        "theme_desc": "切换亮色和暗色主题",
        "language_label": "界面语言",
        "language_desc": "切换界面语言",
        "output_language_label": "输出语言",
        "output_language_desc": "模型回答使用的语言",
        "output_lang_auto": "跟随界面",
        "output_lang_zh": "中文",
        "output_lang_en": "英文",
        "llm_settings": "大模型设置",
        "api_key": "API Key",
        "base_url": "Base URL",
        "models": "模型",
        "streaming": "流式输出",
        "temperature": "温度",
        "max_tokens": "最大令牌数",
        "timeout": "超时 (秒)",
        "save": "保存",
        "save_success": "保存成功",
        "settings_saved": "设置已保存",
        "api_key_saved": "API Key 配置已更新",
        "test": "测试",
        "on": "开",
        "off": "关",
        "back": "返回",
        "web_ctx_forward": "前进",
        "web_ctx_reload": "重新加载",
        "web_ctx_copy": "复制",
        "web_ctx_paste": "粘贴",
        "web_ctx_cut": "剪切",
        "web_ctx_save_page": "保存页面",
        "web_ctx_view_source": "查看网页源代码",
        "n_models": "{n} 个模型",
        "no_history": "暂无历史记录",
        "history_title": "评价历史记录",
        "test_to_discover": "测试连接以发现可用模型",
        "no_models_found": "未从 API 发现模型",
        "missing_key_url": "请输入 API Key 和 Base URL",
        "testing": "测试中",
        "connecting": "正在连接 API...",
        "test_success": "连接成功",
        "test_failed": "连接失败",
        "select_models": "选择模型",
        "add_selected": "添加所选",
        "cancel": "取消",
        "new_task_confirm": "确定要开始新任务吗？\n当前进度将被清空。",
        "new_task_title": "新任务",
        "confirm": "确定",
        "home": "主页",
        "menu": "菜单",
        "chat_thinking": "思考中...",
        "chat_error": "对话出错",
        "no_llm_configured": "请先在设置中配置大模型",
        "err_timeout": "请求超时，请在 设置 → LLM Settings → 当前供应商 中增大 Timeout 值（当前 {timeout}s）",
        "err_auth": "认证失败，请在 设置 → LLM Settings 中检查 API Key 是否正确",
        "err_rate_limit": "请求频率超限，请稍后重试，或在设置中切换其他模型",
        "err_connection": "无法连接到模型服务，请检查网络或在 设置 → LLM Settings 中确认 Base URL 是否正确",
        "err_model_not_found": "模型不存在，请在 设置 → LLM Settings 中重新选择可用模型",
        "err_insufficient_quota": "API 额度不足，请检查账户余额或更换 API Key",
        "select_model": "选择模型",
        "no_model": "未配置模型",
        "history_panel": "历史记录",
        "delete": "删除",
        "clear_all": "清空全部",
        "delete_confirm": "确定删除此记录？",
        "clear_confirm": "确定清空所有历史记录？",
        "no_records": "暂无记录",
        "drop_file_hint": "拖拽文件到此处",
        "file_attached": "已附加文件：{name}",

        "chat_history": "对话历史",
        "chat_history_title": "聊天历史",
        "no_chat_history": "暂无对话记录",
        "untitled_chat": "未命名对话",
        "copy_content": "复制内容",
        "copy_success": "已复制到剪贴板",
        "download_word": "下载为 Word",
        "download_success": "已保存为 Word 文档",
        "download_fail": "保存失败",
        "interrupt": "中断",
        "send": "发送",
        "stop_chat": "中断对话",
        "search_model": "搜索模型",
        "all": "全部",
        "favorites": "收藏",
        "select_model_first": "请先选择模型",
        "view": "查看",
        "view_detail": "查看详情",
        "record_detail": "记录详情",
        "history_window_title": "评价历史记录",
        "rename": "重命名",
        "rename_record": "重命名记录",
        "new_title": "新标题",
        "type_eval": "评价",
        "type_chat": "对话",
        "filter_all": "全部",
        "close": "关闭",
        "open_in_main": "在主界面打开",
        "chat_archived": "对话已归档",
        "parsing": "解析中",
        "ready": "已就绪",
        "remove_file": "移除文件",

        "clear": "清除",
        "clear_success": "已清除",
        "provider_cleared": "当前供应商配置已清除",

        "about": "关于",
        "about_body": (
            "智能评价系统（桌面版）是在复旦大学国家智能评价与治理实验基地研制的"
            "智能评价系统（Pro版）框架下，根据复旦大学赵星团队研究的\u201c数智人\u201d理论、"
            "\u201c智能学术评价\u201d方法、智能模型、算法与创新机制，优选Pro版部分创新算法和"
            "基础功能，由中国科学院文献情报中心李杰团队参与复旦大学团队协同研发的"
            "用户使用版本。本系统可供用户进行便捷化、轻量化的学术成果智能评价探索、"
            "实验和应用。"
        ),
        "about_contact_prefix": "联系邮件：",
        "about_contact_person": "（程老师）",
        "beamplot_weighted": "使用年龄加权",
        "beamplot_help_title": "Beamplot 图表说明",
        "beamplot_ai_placeholder": "AI分析结果将显示在这里...\n\n在Interactive模式下，点击图表数据点或框选区域，然后点击 AI Panel 触发AI分析。",
        "beamplot_help_body": (
            "Beamplot图中下方的 x 轴表示论文的被引次数，y 轴则按发表年份分布这些论文。"
            "研究者的每一篇论文都以黑色菱形标记呈现。某一发表年份对应的线条"
            "（即“波束”），可视化了该年发表论文的被引次数范围。线条下方的黑色三角形"
            "表示该年发表论文的被引次数中位数。黑色虚线是所有年份的被引次数中位数。"
            "上方的 x 轴显示每年的论文数量。红色圆圈表示某一年的发表论文数量，"
            "红色虚线则是每年发表论文数量的中位数。"
        ),
        "beamplot_close": "关闭",
        "beamplot_process_failed": "处理失败",
        "beamplot_done": "完成",
        "beamplot_data_refreshed_title": "数据已更新",
        "beamplot_data_refreshed_content": "Metrics 指标已重新计算，图表已重新绘制。",
        "beamplot_select_wos": "选择 WoS 文件",
        "beamplot_need_file": "请先选择 WoS 文件。",
        "beamplot_file_missing": "所选文件不存在。",
        "beamplot_no_wos_files": "所选路径中未找到 WoS 文本文件（.txt/.ciw/.wos）。",
        "beamplot_default_selected": "已选择默认 Robin Haunschild WoS 数据。",
        "beamplot_default_missing": "默认 Robin Haunschild 数据不存在。",
        "beamplot_interactive_ready": "Interactive Beamplot 已生成。点击数据点或框选区域与AI交互。",
        "beamplot_ready": "Beamplot 已生成。",
        "beamplot_save_missing": "当前没有可保存的图。",
        "beamplot_save_title": "保存 Beamplot 图片",
        "beamplot_saved": "图片已保存并写入历史记录。",
        "beamplot_yes": "是",
        "beamplot_no": "否",
        "beamplot_summary_title": "统计摘要",
        "beamplot_summary_paper_count": "论文数量",
        "beamplot_summary_year_range": "年份范围",
        "beamplot_summary_weighted": "是否年龄加权",
        "beamplot_summary_global_median": "全局引用中位数",
        "beamplot_summary_pub_median": "发文量中位数",
        "beamplot_summary_pub_scale": "发文量缩放因子",
        "beamplot_summary_yearly_title": "逐年统计",
        "beamplot_summary_yearly_line": "{year}: 数量={count}, 最小={min}, 中位数={median}, 最大={max}",
        "history_detail_title": "标题",
        "history_detail_time": "时间",
        "history_detail_image": "图片",
        "history_detail_image_exists": "图片存在",
        "history_detail_image_yes": "是",
        "history_detail_image_no": "否",
        "history_detail_beamplots": "Beamplots",
        "history_detail_ai": "AI 分析",
        "history_detail_qa": "问答",
        "history_detail_question": "问",
        "history_detail_answer": "答",
        "beamplot_selected_citation": "已选择 {year} 年引用次数为 {citations} 的文献点。",
        "beamplot_selected_median": "已选择 {year} 年引用中位数点（{median}）。",
        "beamplot_selected_publication": "已选择 {year} 年发文量点（{count} 篇）。",
        "beamplot_pub_info_title": "{year}   {count} 篇文献   总引用: {total}",
        "beamplot_pub_info_title_weighted": "{year}   {count} 篇文献   年龄加权总引用: {total}",
        "beamplot_selected_point": "已选择一个图表数据点。",
        "beamplot_selected_region_stats": "已选择 {count} 个数据点。引用次数范围：{min_citations} - {max_citations}，平均引用：{avg_citations}。",
        "beamplot_selected_region_years": "已框选 {count} 个数据点，年份范围：{years}。",
        "beamplot_selected_region": "已框选 {count} 个数据点。{range_desc}",
        "beamplot_placeholder_interactive": "点击 “Beamplots Viz.” 渲染交互图",
        "beamplot_plot_hint_line1": "加载数据后，请点击",
        "beamplot_plot_hint_line2": "“Beamplots Viz.” 生成 Beamplot",
        "beamplot_upload_loaded": "已加载：{name}",
        "beamplot_upload_loaded_multi": "{count} 个文件",
        "beamplot_upload_loaded_folder": "{name}（{count} 个文件）",
        "beamplot_upload_loaded_sub": "点击 Beamplots Viz. 渲染图形",
        "beamplot_plot_weighted_note": "图表显示：当前已启用年龄加权，菱形/波束位置按加权被引次数绘制；指标与交互数据均为原始被引次数。",
        "beamplot_interactive_title": "交互式 Beamplot",
        "beamplot_y_axis": "发表年份",
        "beamplot_x_axis_citations": "被引次数",
        "beamplot_year": "年份",
        "beamplot_citations": "被引次数",
        "beamplot_median": "中位数",
        "beamplot_publications": "发文量",
        "beamplot_pointer_tooltip": "鼠标点选",
        "beamplot_citation_median": "引用中位数",
        "beamplot_pub_median": "发文量中位数",
        "beamplot_data": "数据",
        "beamplot_settings": "设置",
        "beamplot_mode": "模式",
        "beamplot_static": "静态",
        "beamplot_interactive": "交互",
        "beamplot_metrics": "指标",
        "beamplot_legend": "图例",
        "beamplot_upload": "上传",
        "beamplot_upload_hint": "点击上传 WoS 文件",
        "beamplot_upload_sub": "或拖拽文件到此处",
        "beamplot_export": "导出",
        "beamplot_ai_panel": "AI 面板",
        "beamplot_new_chat": "新对话",
        "beamplot_chat_placeholder": "输入消息，或询问当前 Beamplot 分析",
        "beamplot_legend_single": "单篇论文引用次数点",
        "beamplot_legend_range": "某一年论文引用次数范围",
        "beamplot_legend_median": "某一年引用次数中位数",
        "beamplot_legend_publication": "某一年发文量",
        "beamplot_legend_pub_median": "每年发文量中位数",
        "publication_list_title": "Publications",
        "publication_year_filter": "年份",
        "publication_all_years": "全部年份",
        "publication_stats_line": "（发文量={count}; 时间跨度={span}）",
    },
    "en_US": {
        "app_title": "Intelligent Evaluation System",
        "app_subtitle": "AIGC-powered academic paper evaluation",

        "upload_hint": "Drag file here or Click to upload\n\nThen click a left-side action, or just chat below",
        "upload_btn": "Upload File",
        "file_ready": "File ready",
        "file_loaded": "Loaded",
        "file_loaded_hint": "✓ {filename}\n\nClick a left-side action, or chat directly below",
        "select_pdf": "Select PDF File",
        "pdf_filter": "PDF Files (*.pdf)",

        "new_task": "New Task",
        "history": "History",

        "basic": "1. Basic Evaluation",
        "advanced": "2. Advanced Evaluation",
        "summary": "3. Evaluation Summary",

        "eval_request": "Please run the following on the current paper: {name}",
        "scoring": "Paper Scoring",
        "content_eval": "Content Evaluation",
        "ensemble": "Ensemble Learning",
        "rag": "Retrieval-Augmented\nGeneration",
        "reflexion": "Reflexion",
        "role_aware": "Role-Aware Reasoning",
        "adversarial": "Adversarial Criticism",
        "innovation": "Innovation Comparison",
        "comprehensive": "Comprehensive\nEvaluation",

        "chatbot": "IES Outputs",
        "input_placeholder": "Type a message, or drop a PDF here (after upload, click a left action or chat directly)",
        "placeholder_title": "Intelligent Evaluation System",
        "placeholder_desc": (
            "\nAn AIGC-based assessment system with intelligent evaluation.\n"
            "It can automatically analyze, evaluate, and provide\n"
            "suggestions to improve the accuracy, efficiency,\n"
            "and objectivity of evaluations."
        ),

        "file_load_success": "File loaded successfully",
        "file_load_fail": "Failed to load file",
        "evaluating": "Evaluating...",
        "eval_complete": "Evaluation complete",
        "eval_error": "Evaluation error",
        "stopping": "Stopping...",
        "stopped": "Stopped",
        "eval_stopped_msg": "\n\n---\n**[ Evaluation stopped by user ]**",
        "upload_first": "Please upload a PDF file first",
        "eval_running": "Evaluation is already running",
        "abort_eval_confirm": "An evaluation is currently running. Abort and switch?",
        "hint": "Notice",
        "stop_eval": "Stop evaluation",

        "settings": "Settings",
        "settings_subtitle": "Personalize your IES experience",
        "appearance": "Appearance",
        "theme": "Theme",
        "theme_desc": "Toggle between light and dark theme",
        "language_label": "UI Language",
        "language_desc": "Switch interface language",
        "output_language_label": "Output Language",
        "output_language_desc": "Language used in model responses",
        "output_lang_auto": "Follow UI",
        "output_lang_zh": "Chinese",
        "output_lang_en": "English",
        "llm_settings": "LLM Settings",
        "api_key": "API Key",
        "base_url": "Base URL",
        "models": "Models",
        "streaming": "Streaming",
        "temperature": "Temperature",
        "max_tokens": "Max Tokens",
        "timeout": "Timeout (s)",
        "save": "Save",
        "save_success": "Saved",
        "settings_saved": "Settings saved",
        "api_key_saved": "API Key configuration updated",
        "test": "Test",
        "on": "On",
        "off": "Off",
        "back": "Back",
        "web_ctx_forward": "Forward",
        "web_ctx_reload": "Reload",
        "web_ctx_copy": "Copy",
        "web_ctx_paste": "Paste",
        "web_ctx_cut": "Cut",
        "web_ctx_save_page": "Save page",
        "web_ctx_view_source": "View page source",
        "n_models": "{n} model(s)",
        "no_history": "No evaluation history yet",
        "history_title": "Evaluation History",
        "test_to_discover": "Test connection to discover models",
        "no_models_found": "No models found from API",
        "missing_key_url": "Please enter API Key and Base URL",
        "testing": "Testing",
        "connecting": "Connecting to API...",
        "test_success": "Connection successful",
        "test_failed": "Connection failed",
        "select_models": "Select Models",
        "add_selected": "Add Selected",
        "cancel": "Cancel",
        "new_task_confirm": "Start a new task?\nCurrent progress will be cleared.",
        "new_task_title": "New Task",
        "confirm": "Confirm",
        "home": "Home",
        "menu": "Menu",
        "chat_thinking": "Thinking...",
        "chat_error": "Chat error",
        "err_timeout": "Request timed out. Go to Settings \u2192 LLM Settings \u2192 current provider and increase the Timeout value (currently {timeout}s)",
        "err_auth": "Authentication failed. Please check your API Key in Settings \u2192 LLM Settings",
        "err_rate_limit": "Rate limit exceeded. Please wait and retry, or switch to a different model in Settings",
        "err_connection": "Cannot connect to model service. Check your network or verify the Base URL in Settings \u2192 LLM Settings",
        "err_model_not_found": "Model not found. Please select a valid model in Settings \u2192 LLM Settings",
        "err_insufficient_quota": "Insufficient API quota. Please check your account balance or use a different API Key",
        "no_llm_configured": "Please configure a LLM provider in Settings first",
        "select_model": "Select Model",
        "no_model": "No model configured",
        "history_panel": "History",
        "delete": "Delete",
        "clear_all": "Clear All",
        "delete_confirm": "Delete this record?",
        "clear_confirm": "Clear all history records?",
        "no_records": "No records",
        "drop_file_hint": "Drop file here",
        "file_attached": "Attached: {name}",

        "chat_history": "Chat History",
        "chat_history_title": "Chat History",
        "no_chat_history": "No chat records yet",
        "untitled_chat": "Untitled Chat",
        "copy_content": "Copy Content",
        "copy_success": "Copied to clipboard",
        "download_word": "Download as Word",
        "download_success": "Saved as Word document",
        "download_fail": "Save failed",
        "interrupt": "Stop",
        "send": "Send",
        "stop_chat": "Interrupt chat",
        "search_model": "Search model",
        "all": "All",
        "favorites": "Favorites",
        "select_model_first": "Please select a model first",
        "view": "View",
        "view_detail": "View Detail",
        "record_detail": "Record Detail",
        "history_window_title": "Evaluation History",
        "rename": "Rename",
        "rename_record": "Rename Record",
        "new_title": "New title",
        "type_eval": "Eval",
        "type_chat": "Chat",
        "filter_all": "All",
        "close": "Close",
        "open_in_main": "Open in main view",
        "chat_archived": "Chat archived",
        "parsing": "Parsing",
        "ready": "Ready",
        "remove_file": "Remove file",

        "clear": "Clear",
        "clear_success": "Cleared",
        "provider_cleared": "Provider configuration cleared",

        "about": "About",
        "about_body": (
            "Intelligent Evaluation System (Desktop Version) is a user-oriented edition "
            "developed under the framework of the Intelligent Evaluation System (Pro "
            "Version), originally created at the National Experiment Base for the "
            "Intelligent Evaluation & Governance at Fudan University. Building upon the "
            "\"Digital-Intelligent Human\" theory, intelligent academic evaluation "
            "methodologies, models, algorithms, and innovation mechanisms "
            "developed by the Zhao Xing research team, this Preview Version "
            "selectively incorporates key innovative algorithms and core functionalities "
            "from the Pro Version. It has been collaboratively developed by the Li Jie "
            "team from the National Science Library, Chinese Academy of Sciences in "
            "partnership with the Fudan University team. This system is designed to "
            "provide users with a convenient and lightweight platform for exploring, "
            "experimenting with, and applying intelligent evaluation of academic "
            "outputs."
        ),
        "about_contact_prefix": "Contact Email: ",
        "about_contact_person": " (Ms. Cheng)",
        "beamplot_weighted": "Age weighted",
        "beamplot_help_title": "Beamplot Description",
        "beamplot_ai_placeholder": "AI analysis results will appear here.\n\nIn Interactive mode, click a data point or select a region, then click AI Panel to start AI analysis.",
        "beamplot_help_body": (
            "In a Beamplot, the bottom x-axis shows citation counts, while the y-axis "
            "distributes publications by publication year. Each publication is shown as "
            "a black diamond. The line for each publication year, or beam, visualizes "
            "the citation range of papers published in that year. The black triangle "
            "below the line marks the citation median for that year. The black dashed "
            "line is the citation median across all years. The top x-axis shows the "
            "number of publications per year. Red circles indicate the number of "
            "publications in a given year, and the red dashed line marks the yearly "
            "publication-count median."
        ),
        "beamplot_close": "Close",
        "beamplot_process_failed": "Failed",
        "beamplot_done": "Done",
        "beamplot_data_refreshed_title": "Data Updated",
        "beamplot_data_refreshed_content": "Metrics recalculated and plots redrawn.",
        "beamplot_select_wos": "Select WoS File",
        "beamplot_need_file": "Please select a WoS file first.",
        "beamplot_file_missing": "The selected file does not exist.",
        "beamplot_no_wos_files": "No WoS text files (.txt/.ciw/.wos) found in the selected path(s).",
        "beamplot_default_selected": "Default Robin Haunschild WoS data selected.",
        "beamplot_default_missing": "Default Robin Haunschild data is missing.",
        "beamplot_interactive_ready": "Interactive Beamplot generated. Click a point or select a region to prepare AI analysis.",
        "beamplot_ready": "Beamplot generated.",
        "beamplot_save_missing": "There is no plot to save.",
        "beamplot_save_title": "Save Beamplot Image",
        "beamplot_saved": "Image saved and added to history.",
        "beamplot_yes": "Yes",
        "beamplot_no": "No",
        "beamplot_summary_title": "Statistical Summary",
        "beamplot_summary_paper_count": "Paper count",
        "beamplot_summary_year_range": "Year range",
        "beamplot_summary_weighted": "Age weighted",
        "beamplot_summary_global_median": "Global citation median",
        "beamplot_summary_pub_median": "Publication-count median",
        "beamplot_summary_pub_scale": "Publication scale factor",
        "beamplot_summary_yearly_title": "Year-by-year statistics",
        "beamplot_summary_yearly_line": "{year}: count={count}, min={min}, median={median}, max={max}",
        "history_detail_title": "Title",
        "history_detail_time": "Time",
        "history_detail_image": "Image",
        "history_detail_image_exists": "Image exists",
        "history_detail_image_yes": "Yes",
        "history_detail_image_no": "No",
        "history_detail_beamplots": "Beamplots",
        "history_detail_ai": "AI Analysis",
        "history_detail_qa": "Q&A",
        "history_detail_question": "Q",
        "history_detail_answer": "A",
        "beamplot_selected_citation": "Selected a {year} publication point with {citations} citations.",
        "beamplot_selected_median": "Selected the {year} citation median point ({median}).",
        "beamplot_selected_publication": "Selected the {year} publication-count point ({count} papers).",
        "beamplot_pub_info_title": "{year}   {count} publications   Total Citations: {total}",
        "beamplot_pub_info_title_weighted": "{year}   {count} publications   Total age-weighted citations: {total}",
        "beamplot_selected_point": "Selected a chart data point.",
        "beamplot_selected_region_stats": "Selected {count} data points. Citation range: {min_citations} - {max_citations}; average citations: {avg_citations}.",
        "beamplot_selected_region_years": "Selected {count} data points across years: {years}.",
        "beamplot_selected_region": "Selected {count} data points. {range_desc}",
        "beamplot_placeholder_interactive": "Click 'Beamplots Viz.' to render interactive chart",
        "beamplot_plot_hint_line1": "After loading data, click",
        "beamplot_plot_hint_line2": "\"Beamplots Viz.\" to generate the beamplot.",
        "beamplot_upload_loaded": "Loaded: {name}",
        "beamplot_upload_loaded_multi": "{count} files",
        "beamplot_upload_loaded_folder": "{name} ({count} files)",
        "beamplot_upload_loaded_sub": "Click Beamplots Viz. to render",
        "beamplot_plot_weighted_note": "Chart display: Age weighting is enabled; diamond/beam positions use weighted citations. Metrics and interaction data use original citation counts.",
        "beamplot_interactive_title": "Interactive Beamplot",
        "beamplot_y_axis": "Publication Year",
        "beamplot_x_axis_citations": "Number of citations",
        "beamplot_year": "Year",
        "beamplot_citations": "Citations",
        "beamplot_median": "Median",
        "beamplot_publications": "Publications",
        "beamplot_pointer_tooltip": "Pointer / point select",
        "beamplot_citation_median": "Citation Median",
        "beamplot_pub_median": "Pub. Median",
        "beamplot_data": "Data",
        "beamplot_settings": "Settings",
        "beamplot_mode": "Mode",
        "beamplot_static": "Static",
        "beamplot_interactive": "Interactive",
        "beamplot_metrics": "Metrics",
        "beamplot_legend": "Legend",
        "beamplot_upload": "Upload",
        "beamplot_upload_hint": "Click to upload WoS file",
        "beamplot_upload_sub": "or drag files here",
        "beamplot_export": "Export",
        "beamplot_ai_panel": "AI Panel",
        "beamplot_new_chat": "New Chat",
        "beamplot_chat_placeholder": "Type a message, or ask about the current Beamplot analysis",
        "beamplot_legend_single": "Single paper citation count",
        "beamplot_legend_range": "Citation range per year",
        "beamplot_legend_median": "Yearly citation median",
        "beamplot_legend_publication": "Publication count per year",
        "beamplot_legend_pub_median": "Publication count median",
        "publication_list_title": "Publications",
        "publication_year_filter": "Year",
        "publication_all_years": "All Years",
        "publication_stats_line": "(Number of Publications={count}; Timespan={span})",
    },
}

LANG_PROMPT_INSTRUCTION = {
    "zh_CN": "请使用中文直接回答，详细评价，确保内容全面、详尽。",
    "en_US": "Please respond in English directly. Provide a detailed and comprehensive evaluation.",
}


class I18n(QObject):
    """国际化管理单例。

    维护两个独立维度：
      - language: 界面 UI 文本语言 (zh_CN / en_US)
      - output_language: 模型输出语言 (auto / zh / en)，auto 表示跟随 UI 语言
    """

    language_changed = pyqtSignal()
    output_language_changed = pyqtSignal()
    _instance = None

    @classmethod
    def instance(cls):
        if cls._instance is None:
            cls._instance = cls()
        return cls._instance

    def __init__(self):
        super().__init__()
        cfg = load_config()
        self._language = cfg.get("language", "en_US")
        self._output_language = cfg.get("output_language", "auto")

    @property
    def language(self) -> str:
        return self._language

    @property
    def is_chinese(self) -> bool:
        return self._language.startswith("zh")

    def set_language(self, lang: str):
        if lang != self._language:
            self._language = lang
            cfg = load_config()
            cfg["language"] = lang
            save_config(cfg)
            self.language_changed.emit()

    @property
    def output_language(self) -> str:
        """返回 'auto' / 'zh' / 'en'。"""
        return self._output_language

    def set_output_language(self, lang: str):
        """lang ∈ {'auto', 'zh', 'en'}。"""
        if lang not in ("auto", "zh", "en"):
            return
        if lang != self._output_language:
            self._output_language = lang
            cfg = load_config()
            cfg["output_language"] = lang
            save_config(cfg)
            self.output_language_changed.emit()

    @property
    def effective_output_lang(self) -> str:
        """返回最终生效的输出语言短码 'zh' / 'en'。"""
        if self._output_language in ("zh", "en"):
            return self._output_language
        return "zh" if self.is_chinese else "en"

    def t(self, key: str, **kwargs) -> str:
        text = TRANSLATIONS.get(self._language, TRANSLATIONS["zh_CN"]).get(key, key)
        if kwargs:
            try:
                text = text.format(**kwargs)
            except (KeyError, IndexError):
                pass
        return text

    @property
    def prompt_lang_instruction(self) -> str:
        return LANG_PROMPT_INSTRUCTION.get(self._language, LANG_PROMPT_INSTRUCTION["zh_CN"])

