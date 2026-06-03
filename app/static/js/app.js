/**
 * @fileoverview 应用入口模块 - 负责初始化所有子模块
 * @module app
 * @description 该模块是前端应用的入口点，负责：
 * 1. 导入并暴露所有子模块到全局作用域
 * 2. 在 DOM 加载完成后初始化应用
 */

// ==================== 模块导入 ====================

/** 工具函数模块（状态管理、UI工具等） */
import * as appUtils from './utils.js';

/** 内容发布模块（搜索、生成、发布功能） */
import * as appPublish from './publish.js';

/** 知识库管理模块（增删改查） */
import * as appKnowledge from './knowledge.js';

/** 产品管理模块（产品列表管理） */
import * as appProducts from './products.js';

/** 定时发布模块（定时任务管理） */
import * as appSchedule from './schedule.js';

// ==================== 全局暴露 ====================

/**
 * 将所有模块暴露到全局 window 对象
 * @description 这样做是为了让 HTML 中的 onclick 等事件处理器能够调用模块中的函数
 * 例如：onclick="window.appProducts.editProduct(0)"
 */
window.appUtils = appUtils;
window.appPublish = appPublish;
window.appKnowledge = appKnowledge;
window.appProducts = appProducts;
window.appSchedule = appSchedule;

// ==================== 应用初始化 ====================

/**
 * 应用初始化函数
 * @async
 * @description 按顺序执行以下初始化操作：
 * 1. 加载配置信息和产品列表
 * 2. 加载知识库数据
 * 3. 加载产品列表数据
 * 4. 初始化全局事件监听器
 * @returns {Promise<void>}
 */
async function init() {
    await appUtils.loadConfig();
    await appKnowledge.loadKnowledgeBase();
    await appProducts.loadProducts();
    appUtils.initEventListeners();
}

// ==================== 启动应用 ====================

/**
 * 根据文档加载状态决定何时初始化
 * @description 如果 DOM 尚未加载完成，等待 DOMContentLoaded 事件
 * 如果已经加载完成（例如脚本在页面底部），直接执行初始化
 */
if (document.readyState === 'loading') {
    document.addEventListener('DOMContentLoaded', init);
} else {
    init();
}
