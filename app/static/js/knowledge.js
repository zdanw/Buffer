/**
 * @fileoverview 知识库管理模块 - 提供知识库条目的增删改查功能
 * @module knowledge
 * @description 该模块负责管理知识库内容，包括：
 * 1. 加载和渲染知识库条目
 * 2. 添加新条目（支持 AI 生成文案）
 * 3. 编辑和删除现有条目
 * 4. 搜索和筛选功能
 */

import { state, showStatus } from './utils.js';

// ==================== 条目添加功能 ====================

/**
 * 添加新条目到知识库
 * @async
 * @description 从表单收集数据，验证后通过 FormData 上传图片和文本内容
 * @returns {Promise<void>}
 */
async function addNewEntry() {
    // 获取表单数据
    const productName = document.getElementById('newProductName').value.trim();
    const content = document.getElementById('newContent').value.trim();
    const prompt = document.getElementById('newPrompt').value.trim();
    const fileInput = document.getElementById('newImageFile');
    const submitBtn = document.getElementById('addToKnowledgeBtn');
    
    // 验证必填字段
    if (!productName || !content || !prompt) {
        showStatus('请填写所有必填字段', 'error');
        return;
    }
    
    // 验证图片文件
    if (!fileInput.files || fileInput.files.length === 0) {
        showStatus('请选择图片文件', 'error');
        return;
    }
    
    // 构建 FormData 用于文件上传
    const formData = new FormData();
    formData.append('产品名称', productName);
    formData.append('文案内容', content);
    formData.append('prompt', prompt);
    formData.append('file', fileInput.files[0]);
    
    // 设置按钮加载状态
    submitBtn.disabled = true;
    submitBtn.textContent = '添加中...';
    
    try {
        const response = await fetch('/api/entries', {
            method: 'POST',
            body: formData
        });
        
        const data = await response.json();
        
        if (data.status === 'success') {
            showStatus('添加成功！新内容已保存到知识库', 'success');
            // 清空表单
            document.getElementById('newProductName').value = '';
            document.getElementById('newContent').value = '';
            document.getElementById('newPrompt').value = '';
            document.getElementById('newImageFile').value = '';
            document.getElementById('imagePreview').style.display = 'none';
            // 重新加载知识库列表
            loadKnowledgeBase();
        } else {
            showStatus('添加失败: ' + data.error, 'error');
        }
    } catch (error) {
        showStatus('添加失败: ' + error.message, 'error');
    } finally {
        // 恢复按钮状态
        submitBtn.disabled = false;
        submitBtn.textContent = '添加到知识库';
    }
}

/**
 * 为知识库生成文案内容
 * @async
 * @description 调用 AI 接口，根据产品名称和描述自动生成社交媒体文案
 * @returns {Promise<void>}
 */
async function generateContentForKnowledge() {
    const productSelect = document.getElementById('newProductName');
    const productName = productSelect.value.trim();
    
    if (!productName) {
        showStatus('请选择产品', 'error');
        return;
    }
    
    // 获取选中产品的描述信息
    const selectedOption = productSelect.options[productSelect.selectedIndex];
    const productDescription = selectedOption ? selectedOption.getAttribute('data-description') || '' : '';
    
    // 设置按钮加载状态
    const btn = document.getElementById('generateContentBtn');
    btn.disabled = true;
    btn.textContent = '正在生成...';
    
    try {
        const response = await fetch('/api/generate-content', {
            method: 'POST',
            headers: { 'Content-Type': 'application/json' },
            body: JSON.stringify({
                '产品名称': productName,
                '产品描述': productDescription
            })
        });
        
        const data = await response.json();
        
        if (data.error) {
            showStatus('生成失败: ' + data.error, 'error');
            return;
        }
        
        // 填充生成的内容到表单
        document.getElementById('newContent').value = data['文案内容'] || '';
        document.getElementById('newPrompt').value = data['prompt'] || '';
        
        showStatus('文案生成成功！请补充图片后添加到知识库', 'success');
        
    } catch (error) {
        showStatus('生成失败: ' + error.message, 'error');
    } finally {
        // 恢复按钮状态
        btn.disabled = false;
        btn.textContent = '✨ 生成文案';
    }
}

// ==================== 数据加载与渲染 ====================

/**
 * 从后端加载知识库数据
 * @async
 * @description 获取所有知识库条目并存储到全局状态
 * @returns {Promise<void>}
 */
async function loadKnowledgeBase() {
    try {
        const response = await fetch('/api/entries');
        const data = await response.json();
        state.allKnowledgeEntries = data.entries;
        renderKnowledgeBase();
    } catch (error) {
        console.error('加载知识库失败:', error);
    }
}

/**
 * 渲染知识库列表到页面
 * @description 根据搜索关键词筛选并渲染知识库条目
 */
function renderKnowledgeBase() {
    // 获取搜索关键词
    const searchTerm = document.getElementById('knowledgeSearch').value.toLowerCase();
    const container = document.getElementById('knowledgeList');
    
    // 根据关键词筛选条目
    let filtered = state.allKnowledgeEntries;
    if (searchTerm) {
        filtered = state.allKnowledgeEntries.filter(item => 
            item['产品名称'].toLowerCase().includes(searchTerm) ||
            item['文案内容'].toLowerCase().includes(searchTerm) ||
            (item['标签'] && item['标签'].some(tag => tag.toLowerCase().includes(searchTerm)))
        );
    }
    
    // 处理空列表情况
    if (filtered.length === 0) {
        container.innerHTML = '<p style="color: #666;">知识库为空</p>';
        return;
    }
    
    // 生成条目列表 HTML
    container.innerHTML = filtered.map(item => {
        const imageUrl = item['image_url'] || 'https://via.placeholder.com/80x80?text=暂无图片';
        
        return `
            <div class="knowledge-item">
                <div style="display: flex; gap: 15px;">
                    <img src="${imageUrl}" alt="${item['产品名称']}" 
                         style="width: 80px; height: 80px; object-fit: cover; border-radius: 8px;" />
                    <div style="flex: 1;">
                        <h4>${item['产品名称']}</h4>
                        <p>${item['文案内容'].substring(0, 80)}...</p>
                        <div class="item-meta">
                            来源: ${item['来源'] || '未知'} | 
                            发布次数: ${item['发布次数'] || 0} |
                            ${item['创建时间'] ? '创建: ' + new Date(item['创建时间'] * 1000).toLocaleString('zh-CN') : ''}
                        </div>
                        <div class="knowledge-item-actions">
                            <button class="btn btn-primary btn-sm" onclick="window.appKnowledge.editEntry('${item['id']}')">编辑</button>
                            <button class="btn btn-danger btn-sm" onclick="window.appKnowledge.deleteEntry('${item['id']}')">删除</button>
                        </div>
                    </div>
                </div>
            </div>
        `;
    }).join('');
}

// ==================== 条目编辑功能 ====================

/**
 * 打开编辑条目的模态框
 * @param {string} id - 要编辑的条目 ID
 * @description 从全局状态查找条目数据并填充到编辑表单
 */
function editEntry(id) {
    // 从全局状态查找条目
    const entry = state.allKnowledgeEntries.find(e => e['id'] === id);
    if (!entry) return;
    
    // 保存当前编辑的条目引用
    state.currentEditEntry = entry;
    
    // 填充表单数据
    document.getElementById('editProductName').value = entry['产品名称'];
    document.getElementById('editContent').value = entry['文案内容'];
    document.getElementById('editPrompt').value = entry['prompt'];
    
    // 设置图片预览
    const imageUrl = entry['image_url'] || '';
    document.getElementById('editImageUrl').value = imageUrl;
    document.getElementById('editImagePreview').src = imageUrl || 'https://via.placeholder.com/200x200?text=暂无图片';
    
    // 显示编辑模态框
    document.getElementById('editModal').classList.add('active');
}

/**
 * 保存编辑后的条目
 * @async
 * @description 收集表单数据并调用 API 更新条目
 * @returns {Promise<void>}
 */
async function saveEdit() {
    // 收集表单数据
    const productName = document.getElementById('editProductName').value.trim();
    const content = document.getElementById('editContent').value.trim();
    const prompt = document.getElementById('editPrompt').value.trim();
    const imageUrl = document.getElementById('editImageUrl').value.trim();
    
    // 验证必填字段
    if (!productName || !content || !prompt) {
        showStatus('请填写所有必填字段', 'error');
        return;
    }
    
    try {
        const updateData = {
            产品名称: productName,
            文案内容: content,
            prompt: prompt,
            image_url: imageUrl
        };
        
        const response = await fetch(`/api/entries/${state.currentEditEntry['id']}`, {
            method: 'PUT',
            headers: { 'Content-Type': 'application/json' },
            body: JSON.stringify(updateData)
        });
        
        const data = await response.json();
        
        if (data.status === 'success') {
            showStatus('更新成功！', 'success');
            // 关闭模态框并重新加载列表
            document.getElementById('editModal').classList.remove('active');
            state.currentEditEntry = null;
            loadKnowledgeBase();
        } else {
            showStatus('更新失败: ' + data.error, 'error');
        }
    } catch (error) {
        showStatus('更新失败: ' + error.message, 'error');
    }
}

// ==================== 条目删除功能 ====================

/**
 * 删除知识库条目
 * @async
 * @param {string} id - 要删除的条目 ID
 * @description 显示确认对话框，确认后调用 API 删除条目
 * @returns {Promise<void>}
 */
async function deleteEntry(id) {
    // 确认删除
    if (!confirm('确定要删除这个条目吗？')) return;
    
    try {
        const response = await fetch(`/api/entries/${id}`, {
            method: 'DELETE'
        });
        
        const data = await response.json();
        
        if (data.status === 'success') {
            showStatus('删除成功！', 'success');
            loadKnowledgeBase();
        } else {
            showStatus('删除失败: ' + data.error, 'error');
        }
    } catch (error) {
        showStatus('删除失败: ' + error.message, 'error');
    }
}

// ==================== 模块导出 ====================

export {
    addNewEntry,
    loadKnowledgeBase,
    renderKnowledgeBase,
    editEntry,
    saveEdit,
    deleteEntry,
    generateContentForKnowledge
};
