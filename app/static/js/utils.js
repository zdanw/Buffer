/**
 * @fileoverview 工具函数模块 - 包含全局状态管理和通用工具函数
 * @module utils
 * @description 该模块提供了整个应用所需的共享状态、状态消息显示、配置加载、标签页切换等通用功能
 */

// ==================== 全局状态存储 ====================

/**
 * 应用全局状态对象
 * @typedef {Object} AppState
 * @property {Object} config - 应用配置信息
 * @property {Array} config.valid_products - 有效产品列表
 * @property {Array} products - 产品列表
 * @property {string} currentMode - 当前发布模式 ('auto' 或 'semi_auto')
 * @property {Object} currentData - 当前生成的内容数据
 * @property {Object|null} selectedProduct - 当前选中的产品
 * @property {Array} searchResultsData - 搜索结果数据
 * @property {Array} allKnowledgeEntries - 所有知识库条目
 * @property {Object|null} currentEditEntry - 当前正在编辑的条目
 */

/**
 * 全局应用状态
 * @type {AppState}
 */
export const state = {
    config: {
        valid_products: []
    },
    products: [],
    currentMode: 'auto',
    currentData: {},
    selectedProduct: null,
    searchResultsData: [],
    allKnowledgeEntries: [],
    currentEditEntry: null
};

// ==================== UI 工具函数 ====================

/**
 * 显示状态消息提示
 * @param {string} message - 要显示的消息内容
 * @param {string} type - 消息类型 ('success' | 'error' | 'info')
 */
export function showStatus(message, type) {
    const statusDiv = document.getElementById('statusMessage');
    statusDiv.className = `status-message status-${type}`;
    statusDiv.textContent = message;
    statusDiv.style.display = 'block';
    
    // 3秒后自动隐藏消息
    setTimeout(() => {
        statusDiv.style.display = 'none';
    }, 3000);
}

/**
 * 加载应用配置和产品数据
 * @description 同时从后端获取产品列表和配置信息，并初始化产品下拉菜单
 * @async
 * @returns {Promise<void>}
 */
export async function loadConfig() {
    try {
        // 同时发起两个请求，提高效率
        const [productsResponse, configResponse] = await Promise.all([
            fetch('/api/products'),
            fetch('/api/config/info')
        ]);
        
        const productsData = await productsResponse.json();
        const configData = await configResponse.json();
        
        // 更新全局状态
        state.products = productsData.products;
        state.config = configData;
        
        // 填充所有产品下拉菜单（新增和编辑）
        const productSelectIds = ['newProductName', 'editProductName'];
        
        productSelectIds.forEach(id => {
            const selectElement = document.getElementById(id);
            if (selectElement) {
                // 清空并重新填充下拉菜单
                selectElement.innerHTML = '<option value="">选择产品...</option>';
                productsData.products.forEach(product => {
                    const description = product.description || '';
                    selectElement.innerHTML += `<option value="${product.name}" data-description="${description}">${product.name}</option>`;
                });
            }
        });
        
        // 绑定产品选择事件，用于显示产品描述
        const newProductSelect = document.getElementById('newProductName');
        if (newProductSelect) {
            newProductSelect.addEventListener('change', displayProductDescription);
        }
    } catch (error) {
        console.error('加载配置失败:', error);
    }
}

/**
 * 显示选中产品的描述信息
 * @description 当用户在下拉菜单中选择产品时，显示该产品的描述
 */
function displayProductDescription() {
    const selectElement = document.getElementById('newProductName');
    const displayDiv = document.getElementById('productDescriptionDisplay');
    
    if (selectElement && displayDiv) {
        const selectedOption = selectElement.options[selectElement.selectedIndex];
        const description = selectedOption ? selectedOption.getAttribute('data-description') : '';
        
        // 根据是否有描述更新样式和内容
        if (description) {
            displayDiv.textContent = description;
            displayDiv.style.background = '#f0f8f0';
            displayDiv.style.borderColor = '#d4edda';
        } else {
            displayDiv.textContent = '请选择产品以查看描述';
            displayDiv.style.background = '#f8f9fa';
            displayDiv.style.borderColor = '#eee';
        }
    }
}

/**
 * 切换标签页
 * @param {string} tab - 要切换到的标签页名称 ('publish' | 'knowledge' | 'products')
 */
export function switchTab(tab) {
    // 移除所有标签页的激活状态
    document.querySelectorAll('.tab').forEach(t => t.classList.remove('active'));
    document.querySelectorAll('.tab-content').forEach(c => c.classList.remove('active'));
    
    // 激活选中的标签页
    event.target.classList.add('active');
    document.getElementById(`${tab}-tab`).classList.add('active');
}

// ==================== 图片处理函数 ====================

/**
 * 图片上传前预览
 * @param {Event} event - 文件输入框的 change 事件
 */
export function previewImage(event) {
    const input = event.target;
    const previewContainer = document.getElementById('imagePreview');
    const previewImg = document.getElementById('previewImg');
    
    if (input.files && input.files[0]) {
        const reader = new FileReader();
        
        reader.onload = function(e) {
            previewImg.src = e.target.result;
            previewContainer.style.display = 'block';
        };
        
        // 读取文件为 DataURL
        reader.readAsDataURL(input.files[0]);
    } else {
        previewContainer.style.display = 'none';
    }
}

/**
 * 预览编辑时的图片
 * @description 根据输入的 URL 更新图片预览
 */
export function previewEditImage() {
    const urlInput = document.getElementById('editImageUrl');
    const url = urlInput.value.trim();
    if (url) {
        document.getElementById('editImagePreview').src = url;
    }
}

/**
 * 清除编辑时的图片
 * @description 重置图片 URL 输入框和预览图片
 */
export function clearEditImage() {
    document.getElementById('editImageUrl').value = '';
    document.getElementById('editImagePreview').src = 'https://via.placeholder.com/200x200?text=暂无图片';
}

/**
 * 切换图片来源方式
 * @description 根据用户选择显示/隐藏上传或URL输入区域
 */
export function toggleImageSource() {
    const source = document.querySelector('input[name="imageSource"]:checked').value;
    const uploadSection = document.getElementById('uploadImageSection');
    const urlSection = document.getElementById('urlImageSection');
    
    if (source === 'upload') {
        uploadSection.style.display = 'block';
        urlSection.style.display = 'none';
    } else {
        uploadSection.style.display = 'none';
        urlSection.style.display = 'block';
    }
}

/**
 * 预览URL图片
 * @description 根据输入的URL更新图片预览
 */
export function previewUrlImage() {
    const urlInput = document.getElementById('newImageUrl');
    const url = urlInput ? urlInput.value.trim() : '';

    console.log('🔍 previewUrlImage() 被调用');
    console.log('📝 URL输入值:', url);

    if (!url) {
        alert('请先输入图片URL');
        return;
    }

    // 添加协议前缀（如果缺少）
    let fullUrl = url;
    if (!url.startsWith('http://') && !url.startsWith('https://')) {
        fullUrl = 'https://' + url;
    }

    console.log('✅ 尝试加载图片:', fullUrl);

    // 获取预览容器
    let previewContainer = document.getElementById('urlImagePreview');
    if (!previewContainer) {
        // 如果找不到容器，创建一个
        const urlSection = document.getElementById('urlImageSection');
        if (urlSection) {
            previewContainer = document.createElement('div');
            previewContainer.id = 'urlImagePreview';
            previewContainer.style.marginTop = '10px';
            urlSection.appendChild(previewContainer);
        }
    }

    if (!previewContainer) {
        alert('错误：无法找到或创建预览容器');
        return;
    }

    // 清空容器，创建新的图片元素
    previewContainer.innerHTML = '';
    previewContainer.style.display = 'block';

    const previewImg = document.createElement('img');
    previewImg.id = 'previewUrlImg';
    previewImg.style.maxWidth = '300px';
    previewImg.style.maxHeight = '200px';
    previewImg.style.borderRadius = '8px';
    previewImg.alt = '预览图片';
    
    // 添加加载指示器
    previewImg.style.display = 'none';
    const loadingDiv = document.createElement('div');
    loadingDiv.textContent = '正在加载图片...';
    loadingDiv.style.padding = '20px';
    loadingDiv.style.color = '#666';
    previewContainer.appendChild(loadingDiv);

    // 设置图片源和事件
    previewImg.onload = function() {
        console.log('✅ 图片加载成功');
        loadingDiv.remove();
        previewImg.style.display = 'block';
    };

    previewImg.onerror = function() {
        console.error('❌ 图片加载失败');
        loadingDiv.remove();
        
        // 显示友好的错误信息
        const errorDiv = document.createElement('div');
        errorDiv.style.padding = '15px';
        errorDiv.style.backgroundColor = '#fff3cd';
        errorDiv.style.border = '1px solid #ffc107';
        errorDiv.style.borderRadius = '4px';
        errorDiv.style.marginTop = '10px';
        errorDiv.innerHTML = `
            <strong>⚠️ 图片预览失败</strong><br>
            <small>可能原因：</small><br>
            <small>1. 图片服务器拒绝访问（防盗链/CORS限制）</small><br>
            <small>2. 网络问题</small><br>
            <small>不过不用担心，您仍然可以继续添加这个图片到知识库！</small>
        `;
        previewContainer.appendChild(errorDiv);
        
        // 直接添加图片URL到知识库仍然是可以的，只是预览不了
    };

    previewImg.src = fullUrl;
    previewContainer.appendChild(previewImg);
}

/**
 * 清除URL图片预览
 * @description 重置URL输入框和预览图片
 */
export function clearUrlImage() {
    document.getElementById('newImageUrl').value = '';
    document.getElementById('urlImagePreview').style.display = 'none';
    document.getElementById('previewUrlImg').src = '';
}

// ==================== 模态框管理 ====================

/**
 * 关闭编辑模态框
 * @description 隐藏模态框并清空当前编辑条目的状态
 */
export function closeEditModal() {
    document.getElementById('editModal').classList.remove('active');
    state.currentEditEntry = null;
}

/**
 * 创建通用模态框
 * @param {string} contentHtml - 模态框内容的 HTML 字符串
 * @param {Object} [options={}] - 模态框配置选项
 * @param {string} [options.width='90%'] - 模态框宽度
 * @param {string} [options.maxWidth='450px'] - 模态框最大宽度
 * @param {Function} [options.onClose] - 模态框关闭时的回调函数
 * @returns {Object} 模态框控制对象
 * @returns {HTMLElement} return.modal - 模态框 DOM 元素
 * @returns {HTMLElement} return.content - 内容容器 DOM 元素
 * @returns {Function} return.close - 关闭模态框的方法
 */
export function createModal(contentHtml, options = {}) {
    const { width = '90%', maxWidth = '450px', onClose } = options;
    
    // 创建模态框背景
    const modal = document.createElement('div');
    modal.className = 'generic-modal';
    modal.style.cssText = `
        position: fixed;
        top: 0;
        left: 0;
        width: 100%;
        height: 100%;
        background: rgba(0,0,0,0.5);
        display: flex;
        justify-content: center;
        align-items: center;
        z-index: 1000;
        animation: fadeIn 0.2s ease;
    `;
    
    // 创建内容容器
    const content = document.createElement('div');
    content.style.cssText = `
        background: white;
        border-radius: 12px;
        width: ${width};
        max-width: ${maxWidth};
        max-height: 80vh;
        overflow-y: auto;
        animation: slideIn 0.2s ease;
    `;
    content.innerHTML = contentHtml;
    modal.appendChild(content);
    
    /**
     * 关闭模态框的方法
     */
    const close = () => {
        modal.style.animation = 'fadeOut 0.2s ease';
        setTimeout(() => {
            // 确保元素还在 DOM 中再移除
            if (document.body.contains(modal)) {
                document.body.removeChild(modal);
            }
            if (onClose) onClose();
        }, 200);
    };
    
    // 点击背景关闭
    modal.addEventListener('click', (e) => {
        if (e.target === modal) close();
    });
    
    document.body.appendChild(modal);
    
    return {
        modal,
        content,
        close
    };
}

// ==================== 事件初始化 ====================

/**
 * 初始化全局事件监听器
 * @description 设置模式选择、搜索等全局事件监听
 */
export function initEventListeners() {
    console.log('🔧 initEventListeners() 被调用');
    
    // 模式选择事件监听
    document.querySelectorAll('.mode-option').forEach(option => {
        option.addEventListener('click', () => {
            // 重置所有模式选项样式
            document.querySelectorAll('.mode-option').forEach(opt => opt.classList.remove('active'));
            // 激活当前选项
            option.classList.add('active');
            state.currentMode = option.dataset.mode;
            
            // 隐藏预览和结果区域
            document.getElementById('previewSection').classList.remove('active');
            document.getElementById('publishResultSection').classList.remove('active');
        });
    });

    // 知识库搜索监听
    const knowledgeSearch = document.getElementById('knowledgeSearch');
    if (knowledgeSearch) {
        knowledgeSearch.addEventListener('input', () => {
            // 当输入变化时，触发知识库存的重新渲染（在 knowledge 模块中定义）
            if (window.appKnowledge && window.appKnowledge.renderKnowledgeBase) {
                window.appKnowledge.renderKnowledgeBase();
            }
        });
    }

    // 图片来源切换监听
    const imageSourceRadios = document.querySelectorAll('input[name="imageSource"]');
    console.log('📷 找到的图片来源单选框数量:', imageSourceRadios.length);
    imageSourceRadios.forEach(radio => {
        radio.addEventListener('change', (e) => {
            console.log('📷 图片来源切换到:', e.target.value);
            toggleImageSource();
        });
        console.log('✅ 为图片来源单选框添加了事件监听器:', radio.value);
    });
    
    // 初始化时确保正确显示默认选项
    toggleImageSource();
    console.log('✅ initEventListeners() 完成');
}
