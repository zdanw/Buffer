/**
 * @fileoverview 内容发布模块 - 提供内容搜索、生成和发布功能
 * @module publish
 * @description 该模块是核心业务模块，负责：
 * 1. 产品搜索和选择
 * 2. AI 内容生成（文案 + 图片）
 * 3. 多平台发布（TikTok、Instagram、Facebook）
 * 4. 定时发布支持
 */

import { state, showStatus, setButtonLoading, resetButton, escapeHtml } from './utils.js';

// ==================== 定时发布功能 ====================

/**
 * 获取定时发布时间
 * @returns {string|null} ISO 8601 格式的时间字符串，如果未启用定时则返回 null
 */
function getScheduleTime() {
    const enableSchedule = document.getElementById('enableSchedule');
    if (!enableSchedule.checked) {
        return null;
    }
    
    const scheduleTimeInput = document.getElementById('scheduleTime');
    if (!scheduleTimeInput.value) {
        return null;
    }
    
    // 将 datetime-local 格式转换为 ISO 8601 格式（带时区）
    const date = new Date(scheduleTimeInput.value);
    return date.toISOString();
}

// ==================== 平台选择功能 ====================

/**
 * 获取用户选中的发布平台
 * @returns {Array<string>} 选中的平台 ID 列表
 */
function getSelectedPlatforms() {
    const platforms = [];
    document.querySelectorAll('input[name="publishPlatform"]:checked').forEach(checkbox => {
        platforms.push(checkbox.value);
    });
    return platforms;
}

/**
 * 更新选中平台的显示区域
 * @description 在预览区域显示当前选中的平台名称
 */
function updateSelectedPlatformsDisplay() {
    const platforms = getSelectedPlatforms();
    const platformNames = {
        'tiktok': '🎵 TikTok',
        'instagram': '📷 Instagram',
        'facebook': '📘 Facebook'
    };
    document.getElementById('selectedPlatformsDisplay').innerHTML = 
        platforms.length > 0 ? 
            platforms.map(p => `<span style="margin-right: 10px;">${platformNames[p] || p}</span>`).join('') :
            '未选择任何平台';
}

// ==================== 产品搜索与选择 ====================

/**
 * 搜索产品
 * @async
 * @description 根据关键词搜索知识库中的产品
 * @returns {Promise<void>}
 */
async function searchProducts() {
    const btn = document.getElementById('productSearchBtn');
    setButtonLoading(btn, '搜索中...');
    
    const keyword = document.getElementById('productInput').value.trim();
    if (!keyword) {
        showStatus('请输入产品关键词', 'error');
        resetButton(btn);
        return;
    }

    try {
        const response = await fetch(`/api/search?keyword=${encodeURIComponent(keyword)}`);
        
        if (!response.ok) {
            throw new Error(`HTTP ${response.status}`);
        }
        
        const data = await response.json();
        
        state.searchResultsData = data.results || [];
        
        if (state.searchResultsData.length === 0) {
            document.getElementById('searchResults').innerHTML = '<p style="color: #666;">未找到相关产品</p>';
        } else {
            let html = '';
            state.searchResultsData.forEach((item, index) => {
                const imageUrl = item['image_url'] || 'https://via.placeholder.com/100x100?text=暂无图片';
                const similarityPercent = (item['similarity'] * 100).toFixed(1);
                const compositeScorePercent = item['composite_score'] ? (item['composite_score'] * 100).toFixed(1) : similarityPercent;
                
                const productName = escapeHtml(item['产品名称'] || '');
                const content = escapeHtml(item['文案内容'] || '');
                const tags = item['标签'] && item['标签'].length > 0 ? 
                    '<div class="item-tags">' + item['标签'].map(tag => `<span class="item-tag">${escapeHtml(String(tag))}</span>`).join('') + '</div>' : '';
                
                html += `
                    <div class="search-item" onclick="window.appPublish.selectProduct(${index})">
                        <div style="display: flex; gap: 15px;">
                            <img src="${imageUrl}" alt="${productName}" 
                                 style="width: 100px; height: 100px; object-fit: cover; border-radius: 8px;" />
                            <div style="flex: 1;">
                                <h4>${productName}</h4>
                                <p>文案：${content.substring(0, 50)}...</p>
                                ${tags}
                                <p style="font-size: 0.8rem; color: #999;">
                                    相似度: ${similarityPercent}% | 综合评分: ${compositeScorePercent}% | 发布次数: ${item['发布次数'] || 0}
                                </p>
                            </div>
                        </div>
                    </div>
                `;
            });
            document.getElementById('searchResults').innerHTML = html;
        }
    } catch (error) {
        showStatus('搜索失败: ' + error.message, 'error');
    } finally {
        resetButton(btn);
    }
}

/**
 * 选择产品
 * @param {number} index - 产品在搜索结果列表中的索引
 * @description 将选中的产品信息显示在界面上，并启用操作按钮
 */
function selectProduct(index) {
    if (!state.searchResultsData || !state.searchResultsData[index]) {
        return;
    }
    
    // 保存选中的产品到全局状态
    state.selectedProduct = state.searchResultsData[index];
    document.getElementById('searchResults').innerHTML = '';
    
    // 显示选中的产品信息
    const imageUrl = state.selectedProduct['image_url'] || 'https://via.placeholder.com/100x100?text=暂无图片';
    
    document.getElementById('selectedProductImage').src = imageUrl;
    document.getElementById('selectedProductName').textContent = state.selectedProduct['产品名称'];
    document.getElementById('selectedProductContent').textContent = '文案：' + state.selectedProduct['文案内容'].substring(0, 80) + '...';
    
    // 显示选中区域，启用操作按钮
    document.getElementById('selectedProduct').style.display = 'block';
    document.getElementById('noProductSelected').style.display = 'none';
    document.getElementById('startButton').disabled = false;
    document.getElementById('publishExistingButton').disabled = false;
}

// ==================== 发布功能 ====================

/**
 * 直接发布知识库中已有的内容
 * @async
 * @description 不生成新内容，直接将知识库中的内容发布到选定平台
 * @returns {Promise<void>}
 */
async function publishExistingContent() {
    if (!state.selectedProduct) {
        showStatus('请先选择一个产品', 'error');
        return;
    }
    
    const platforms = getSelectedPlatforms();
    if (platforms.length === 0) {
        showStatus('请至少选择一个发布平台', 'error');
        return;
    }
    
    const btn = document.getElementById('publishExistingButton');
    setButtonLoading(btn, '📤 发布内容');
    
    const scheduleTime = getScheduleTime();
    const immediate = scheduleTime === null;
    
    if (immediate) {
        showStatus('正在立即发布...', 'info');
    } else {
        showStatus('正在定时发布...', 'info');
    }
    
    try {
        const requestBody = {
            text: state.selectedProduct['文案内容'],
            image_url: state.selectedProduct['image_url'],
            platforms: platforms,
            产品名称: state.selectedProduct['产品名称'],
            prompt: state.selectedProduct['prompt'],
            标签: state.selectedProduct['标签'] || [],
            immediate: immediate,
            source: 'knowledge',
            entry_id: state.selectedProduct['id']
        };
        
        if (scheduleTime) {
            requestBody.schedule_time = scheduleTime;
        }
        
        const response = await fetch('/api/publish', {
            method: 'POST',
            headers: { 'Content-Type': 'application/json' },
            body: JSON.stringify(requestBody)
        });
        
        const data = await response.json();
        
        // 显示预览区域
        document.getElementById('generatedImage').src = state.selectedProduct['image_url'] || 'https://via.placeholder.com/400x400?text=暂无图片';
        document.getElementById('generatedContent').textContent = state.selectedProduct['文案内容'];
        
        document.getElementById('previewSection').classList.add('active');
        displayPublishResults(data);
        
        if (data.success_count > 0) {
            showStatus(`直接发布完成，成功${data.success_count}个平台`, 'success');
        } else {
            showStatus('发布失败，请查看详情', 'error');
        }
    } catch (error) {
        showStatus('发布失败: ' + error.message, 'error');
    } finally {
        resetButton(btn);
    }
}

/**
 * 开始内容生成/发布流程
 * @async
 * @description 根据当前模式（自动/半自动）执行不同的流程
 * @returns {Promise<void>}
 */
async function startProcess() {
    if (!state.selectedProduct) {
        showStatus('请先选择一个产品', 'error');
        return;
    }
    
    const platforms = getSelectedPlatforms();
    if (platforms.length === 0) {
        showStatus('请至少选择一个发布平台', 'error');
        return;
    }
    
    const productName = state.selectedProduct['产品名称'];
    
    // 禁用所有操作按钮，防止重复操作
    const startBtn = document.getElementById('startButton');
    const publishBtn = document.getElementById('publishExistingButton');
    const regenerateBtn = document.getElementById('regenerateContentBtn');
    const regenerateImgBtn = document.getElementById('regenerateImageBtn');
    const publishNewBtn = document.getElementById('publishNewButton');
    
    const disableButtons = [startBtn, publishBtn, regenerateBtn, regenerateImgBtn, publishNewBtn];
    disableButtons.forEach(btn => {
        if (btn) {
            btn.disabled = true;
        }
    });
    
    try {
        if (state.currentMode === 'auto') {
            await autoPublish(productName, platforms);
        } else {
            await generateContent(productName);
        }
    } finally {
        // 恢复所有按钮状态
        disableButtons.forEach(btn => {
            if (btn) {
                btn.disabled = false;
            }
        });
    }
}

/**
 * 生成新内容（半自动模式）
 * @async
 * @param {string} productName - 产品名称
 * @returns {Promise<void>}
 */
async function generateContent(productName) {
    showStatus('正在生成内容...', 'info');
    
    try {
        const requestBody = { 
            product_name: productName, 
            mode: 'semi_auto' 
        };
        
        // 如果有选中的条目，传递其ID
        if (state.selectedProduct && state.selectedProduct.id) {
            requestBody.entry_id = state.selectedProduct.id;
        }
        
        const response = await fetch('/api/generate', {
            method: 'POST',
            headers: { 'Content-Type': 'application/json' },
            body: JSON.stringify(requestBody)
        });
        
        const data = await response.json();
        
        if (data.error) {
            showStatus(data.error, 'error');
            return;
        }
        
        // 保存生成的内容到全局状态
        state.currentData = {
            original_entry: data.original_entry,
            generated_content: data.generated_content,
            generated_image: data.generated_image,
            content_prompt: data.content_prompt || '',
            image_prompt: data.image_prompt || ''
        };
        
        // 显示生成的内容
        document.getElementById('generatedImage').src = data.generated_image || 'https://via.placeholder.com/400x400?text=图片生成失败';
        document.getElementById('generatedContent').textContent = data.generated_content || '文案生成失败';
        
        // 显示提示词
        document.getElementById('contentPromptDisplay').textContent = data.content_prompt || '暂无文案提示词';
        document.getElementById('imagePromptDisplay').textContent = data.image_prompt || '暂无图片提示词';
        
        document.getElementById('previewSection').classList.add('active');
        document.getElementById('publishResultSection').classList.remove('active');
        
        updateSelectedPlatformsDisplay();
        showStatus('内容生成完成，请确认后发布', 'success');
    } catch (error) {
        showStatus('生成失败: ' + error.message, 'error');
    }
}

// ==================== 内容重新生成 ====================

/**
 * 重新生成文案
 * @async
 * @returns {Promise<void>}
 */
async function regenerateContent() {
    if (!state.currentData.original_entry) {
        showStatus('请先生成内容', 'error');
        return;
    }
    
    const btn = document.getElementById('regenerateContentBtn');
    setButtonLoading(btn, '🔄 重新生成文案');
    showStatus('正在重新生成文案...', 'info');
    
    try {
        const response = await fetch('/api/regenerate', {
            method: 'POST',
            headers: { 'Content-Type': 'application/json' },
            body: JSON.stringify({ 
                original_entry: state.currentData.original_entry,
                type: 'content'
            })
        });
        
        const data = await response.json();
        state.currentData.generated_content = data.generated_content;
        state.currentData.content_prompt = data.content_prompt || '';
        document.getElementById('generatedContent').textContent = data.generated_content || '文案生成失败';
        document.getElementById('contentPromptDisplay').textContent = data.content_prompt || '暂无文案提示词';
        showStatus('文案重新生成完成', 'success');
    } catch (error) {
        showStatus('重新生成失败: ' + error.message, 'error');
    } finally {
        resetButton(btn);
    }
}

/**
 * 重新生成图片
 * @async
 * @returns {Promise<void>}
 */
async function regenerateImage() {
    if (!state.currentData.original_entry) {
        showStatus('请先生成内容', 'error');
        return;
    }
    
    const btn = document.getElementById('regenerateImageBtn');
    setButtonLoading(btn, '🖼️ 重新生成图片');
    showStatus('正在重新生成图片...', 'info');
    
    try {
        const response = await fetch('/api/regenerate', {
            method: 'POST',
            headers: { 'Content-Type': 'application/json' },
            body: JSON.stringify({ 
                original_entry: state.currentData.original_entry,
                type: 'image'
            })
        });
        
        const data = await response.json();
        state.currentData.generated_image = data.generated_image;
        state.currentData.image_prompt = data.image_prompt || '';
        document.getElementById('generatedImage').src = data.generated_image || 'https://via.placeholder.com/400x400?text=图片生成失败';
        document.getElementById('imagePromptDisplay').textContent = data.image_prompt || '暂无图片提示词';
        showStatus('图片重新生成完成', 'success');
    } catch (error) {
        showStatus('重新生成失败: ' + error.message, 'error');
    } finally {
        resetButton(btn);
    }
}

/**
 * 重新生成全部内容（文案 + 图片）
 * @async
 * @returns {Promise<void>}
 */
async function regenerateBoth() {
    if (!state.currentData.original_entry) {
        showStatus('请先生成内容', 'error');
        return;
    }
    
    const btn = document.getElementById('regenerateBothBtn');
    setButtonLoading(btn, '🔄 重新生成全部');
    showStatus('正在重新生成全部内容...', 'info');
    
    try {
        const response = await fetch('/api/regenerate', {
            method: 'POST',
            headers: { 'Content-Type': 'application/json' },
            body: JSON.stringify({ 
                original_entry: state.currentData.original_entry,
                type: 'both'
            })
        });
        
        const data = await response.json();
        state.currentData.generated_content = data.generated_content;
        state.currentData.generated_image = data.generated_image;
        state.currentData.content_prompt = data.content_prompt || '';
        state.currentData.image_prompt = data.image_prompt || '';
        
        document.getElementById('generatedContent').textContent = data.generated_content || '文案生成失败';
        document.getElementById('generatedImage').src = data.generated_image || 'https://via.placeholder.com/400x400?text=图片生成失败';
        document.getElementById('contentPromptDisplay').textContent = data.content_prompt || '暂无文案提示词';
        document.getElementById('imagePromptDisplay').textContent = data.image_prompt || '暂无图片提示词';
        showStatus('内容重新生成完成', 'success');
    } catch (error) {
        showStatus('重新生成失败: ' + error.message, 'error');
    } finally {
        resetButton(btn);
    }
}

/**
 * 发布生成的新内容
 * @async
 * @returns {Promise<void>}
 */
async function publishContent() {
    const platforms = getSelectedPlatforms();
    
    if (platforms.length === 0) {
        showStatus('请至少选择一个发布平台', 'error');
        return;
    }
    
    const btn = document.getElementById('publishNewButton');
    setButtonLoading(btn, '🚀 发布内容');
    
    const scheduleTime = getScheduleTime();
    const immediate = scheduleTime === null;
    
    if (immediate) {
        showStatus('正在立即发布到社交平台...', 'info');
    } else {
        showStatus('正在定时发布到社交平台...', 'info');
    }
    
    try {
        const requestBody = {
            text: state.currentData.generated_content,
            image_url: state.currentData.generated_image,
            platforms: platforms,
            产品名称: state.currentData.original_entry?.产品名称 || '',
            prompt: state.currentData.original_entry?.prompt || '',
            标签: state.currentData.original_entry?.标签 || [],
            immediate: immediate,
            source: 'new'
        };
        
        if (scheduleTime) {
            requestBody.schedule_time = scheduleTime;
        }
        
        const response = await fetch('/api/publish', {
            method: 'POST',
            headers: { 'Content-Type': 'application/json' },
            body: JSON.stringify(requestBody)
        });
        
        const data = await response.json();
        displayPublishResults(data);
        showStatus(`发布完成，成功${data.success_count}个平台`, 'success');
    } catch (error) {
        showStatus('发布失败: ' + error.message, 'error');
    } finally {
        resetButton(btn);
    }
}

/**
 * 全自动发布模式
 * @async
 * @param {string} productName - 产品名称
 * @param {Array<string>} platforms - 目标平台列表
 * @returns {Promise<void>}
 */
async function autoPublish(productName, platforms) {
    const scheduleTime = getScheduleTime();
    const immediate = scheduleTime === null;
    
    if (immediate) {
        showStatus('全自动模式启动中（立即发布）...', 'info');
    } else {
        showStatus('全自动模式启动中（定时发布）...', 'info');
    }
    
    try {
        const requestBody = { 
            product_name: productName, 
            platforms: platforms, 
            immediate: immediate 
        };
        
        if (scheduleTime) {
            requestBody.schedule_time = scheduleTime;
        }
        
        const response = await fetch('/api/auto_publish', {
            method: 'POST',
            headers: { 'Content-Type': 'application/json' },
            body: JSON.stringify(requestBody)
        });
        
        const data = await response.json();
        
        if (data.error) {
            showStatus(data.error, 'error');
            return;
        }
        
        // 保存生成的内容
        state.currentData = {
            generated_content: data.generated_content,
            generated_image: data.generated_image,
            content_prompt: data.content_prompt || '',
            image_prompt: data.image_prompt || ''
        };
        
        // 显示生成的内容
        document.getElementById('generatedImage').src = data.generated_image || 'https://via.placeholder.com/400x400?text=图片生成失败';
        document.getElementById('generatedContent').textContent = data.generated_content || '文案生成失败';
        document.getElementById('contentPromptDisplay').textContent = data.content_prompt || '暂无文案提示词';
        document.getElementById('imagePromptDisplay').textContent = data.image_prompt || '暂无图片提示词';
        
        document.getElementById('previewSection').classList.add('active');
        displayPublishResults(data);
        showStatus('全自动发布完成', 'success');
    } catch (error) {
        showStatus('自动发布失败: ' + error.message, 'error');
    }
}

/**
 * 显示发布结果
 * @param {Object} data - 发布结果数据
 * @param {Array} data.publish_results - 发布结果列表
 * @param {Array} data.results - 发布结果列表（备选字段）
 */
function displayPublishResults(data) {
    const resultSection = document.getElementById('publishResultSection');
    resultSection.classList.add('active');
    
    let html = '<h3>发布结果</h3>';
    const results = data.publish_results || [];
    if (results.length > 0) {
        results.forEach(result => {
            const statusClass = result.status === 'success' ? 'status-success' : 'status-error';
            const platformName = escapeHtml(result.channel || result.platform || '未知平台');
            const errorMsg = escapeHtml(result.error || '');
            html += `
                <div class="status-message ${statusClass}">
                    <strong>${platformName}</strong><br>
                    ${result.status === 'success' ? '发布成功' : errorMsg || '发布失败'}
                </div>
            `;
        });
    } else {
        html += '<p style="color: #888;">暂无发布结果</p>';
    }
    
    document.getElementById('publishResults').innerHTML = html;
    
    resultSection.scrollIntoView({ behavior: 'smooth' });
}

/**
 * 保存生成的内容到知识库
 */
async function saveToKnowledge() {
    // 验证是否有生成的内容
    if (!state.currentData.generated_content) {
        showStatus('请先生成内容', 'error');
        return;
    }
    
    const btn = document.getElementById('saveToKnowledgeBtn');
    setButtonLoading(btn, '💾 保存中');
    
    showStatus('正在保存到知识库...', 'info');
    
    try {
        const requestBody = {
            product_name: state.currentData.original_entry?.产品名称 || '未命名产品',
            content: state.currentData.generated_content,
            image_url: state.currentData.generated_image || '',
            prompt: state.currentData.original_entry?.prompt || '',
            original_entry_id: state.currentData.original_entry?.id
        };
        
        const response = await fetch('/api/save-to-knowledge', {
            method: 'POST',
            headers: { 'Content-Type': 'application/json' },
            body: JSON.stringify(requestBody)
        });
        
        const data = await response.json();
        
        if (data.success) {
            showStatus(`✅ 保存成功！条目ID: ${data.entry_id}`, 'success');
        } else {
            showStatus('保存失败: ' + (data.error || '未知错误'), 'error');
        }
    } catch (error) {
        showStatus('保存失败: ' + error.message, 'error');
    } finally {
        resetButton(btn);
    }
}


// ==================== 模块导出 ====================

export {
    searchProducts,
    selectProduct,
    publishExistingContent,
    startProcess,
    generateContent,
    regenerateContent,
    regenerateImage,
    regenerateBoth,
    publishContent,
    saveToKnowledge,
    autoPublish,
    displayPublishResults,
    updateSelectedPlatformsDisplay
};
