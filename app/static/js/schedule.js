/**
 * @fileoverview 定时发布模块 - 管理定时发布任务
 * @module schedule
 * @description 该模块负责：
 * 1. 创建、编辑、删除定时发布任务
 * 2. 切换调度类型（间隔模式/Cron模式）
 * 3. 启用/禁用定时任务
 * 4. 手动执行发布测试
 */

import { API_BASE_URL } from './utils.js';

/**
 * 切换调度类型
 * @param {string} type - 调度类型：'interval' 或 'cron'
 */
export function switchScheduleType(type) {
    const intervalSettings = document.getElementById('intervalSettings');
    const cronSettings = document.getElementById('cronSettings');
    const modeOptions = document.querySelectorAll('[data-schedule-type]');
    
    modeOptions.forEach(option => {
        option.classList.toggle('active', option.dataset.scheduleType === type);
    });
    
    if (type === 'interval') {
        intervalSettings.style.display = 'block';
        cronSettings.style.display = 'none';
    } else {
        intervalSettings.style.display = 'none';
        cronSettings.style.display = 'block';
    }
}

/**
 * 创建定时任务
 */
export async function createJob() {
    const name = document.getElementById('scheduleJobName').value || '定时发布任务';
    const scheduleType = document.querySelector('[data-schedule-type].active')?.dataset.scheduleType || 'interval';
    const intervalMinutes = parseInt(document.getElementById('intervalMinutes').value) || 60;
    const cronExpression = document.getElementById('cronExpression').value;
    const platforms = Array.from(document.querySelectorAll('input[name="schedulePlatform"]:checked')).map(el => el.value);
    const countPerRun = parseInt(document.getElementById('countPerRun').value) || 1;
    const maxPublishCount = document.getElementById('maxPublishCount').value ? parseInt(document.getElementById('maxPublishCount').value) : undefined;
    const enabled = document.getElementById('scheduleEnabled').checked;
    
    if (scheduleType === 'cron' && !cronExpression) {
        alert('Cron模式需要输入Cron表达式');
        return;
    }
    
    if (platforms.length === 0) {
        alert('请至少选择一个发布平台');
        return;
    }
    
    const data = {
        name,
        schedule_type: scheduleType,
        interval_minutes: scheduleType === 'interval' ? intervalMinutes : undefined,
        cron_expression: scheduleType === 'cron' ? cronExpression : undefined,
        platforms,
        count_per_run: countPerRun,
        max_publish_count: maxPublishCount,
        enabled
    };
    
    try {
        const response = await fetch(`${API_BASE_URL}/api/schedule/jobs`, {
            method: 'POST',
            headers: {
                'Content-Type': 'application/json'
            },
            body: JSON.stringify(data)
        });
        
        const result = await response.json();
        
        if (response.ok) {
            alert(`定时任务创建成功!\n任务ID: ${result.job_id}`);
            clearScheduleForm();
            await loadJobs();
        } else {
            alert(`创建失败: ${result.error || '未知错误'}`);
        }
    } catch (error) {
        console.error('创建定时任务失败:', error);
        alert('创建定时任务失败，请检查网络连接');
    }
}

/**
 * 清空定时任务表单
 */
function clearScheduleForm() {
    document.getElementById('scheduleJobName').value = '';
    document.getElementById('intervalMinutes').value = 60;
    document.getElementById('cronExpression').value = '';
    document.getElementById('countPerRun').value = 1;
    document.getElementById('maxPublishCount').value = '';
    document.getElementById('scheduleEnabled').checked = true;
    
    switchScheduleType('interval');
    
    document.querySelectorAll('input[name="schedulePlatform"]').forEach(el => {
        el.checked = true;
    });
}

/**
 * 加载定时任务列表
 */
export async function loadJobs() {
    try {
        const response = await fetch(`${API_BASE_URL}/api/schedule/jobs`);
        const result = await response.json();
        
        if (response.ok) {
            renderJobList(result.jobs || []);
        } else {
            console.error('加载定时任务失败:', result.error);
        }
    } catch (error) {
        console.error('加载定时任务失败:', error);
    }
}

/**
 * 渲染定时任务列表
 * @param {Array} jobs - 任务列表
 */
function renderJobList(jobs) {
    const container = document.getElementById('scheduleJobList');
    
    if (!jobs || jobs.length === 0) {
        container.innerHTML = '<p style="text-align: center; color: #888; padding: 20px;">暂无定时任务</p>';
        return;
    }
    
    container.innerHTML = `
        <div style="display: grid; gap: 15px;">
            ${jobs.map(job => `
                <div class="schedule-job-card" data-job-id="${job.job_id}">
                    <div style="display: flex; justify-content: space-between; align-items: flex-start; margin-bottom: 10px;">
                        <div>
                            <h3 style="margin: 0 0 5px 0;">${escapeHtml(job.name)}</h3>
                            <div style="color: #888; font-size: 0.9rem;">
                                <span>${job.schedule_type === 'interval' ? '每 ' + job.interval_minutes + ' 分钟' : 'Cron: ' + job.cron_expression}</span>
                                <span style="margin: 0 10px;">|</span>
                                <span>平台: ${job.platforms.join(', ')}</span>
                                <span style="margin: 0 10px;">|</span>
                                <span>每次发布 ${job.count_per_run} 个产品</span>
                                ${job.max_publish_count ? '<span style="margin: 0 10px;">|</span><span>发布上限: ' + job.max_publish_count + '</span>' : ''}
                            </div>
                        </div>
                        <span class="${job.enabled ? 'status-badge active' : 'status-badge inactive'}">
                            ${job.enabled ? '运行中' : '已禁用'}
                        </span>
                    </div>
                    
                    ${job.next_run_time ? '<div style="color: #666; font-size: 0.85rem; margin-bottom: 10px;">下次执行: ' + formatTime(job.next_run_time) + '</div>' : ''}
                    
                    <div style="display: flex; gap: 10px;">
                        <button class="btn btn-secondary btn-sm" onclick="window.appSchedule.toggleJob('${job.job_id}')">
                            ${job.enabled ? '⏸ 暂停' : '▶ 启动'}
                        </button>
                        <button class="btn btn-info btn-sm" onclick="window.appSchedule.editJob('${job.job_id}')">
                            ✏ 编辑
                        </button>
                        <button class="btn btn-danger btn-sm" onclick="window.appSchedule.deleteJob('${job.job_id}')">
                            🗑 删除
                        </button>
                    </div>
                </div>
            `).join('')}
        </div>
    `;
}

/**
 * 格式化时间字符串
 * @param {string} timeStr - 时间字符串
 * @returns {string} 格式化后的时间
 */
function formatTime(timeStr) {
    try {
        const date = new Date(timeStr);
        return date.toLocaleString('zh-CN', {
            year: 'numeric',
            month: '2-digit',
            day: '2-digit',
            hour: '2-digit',
            minute: '2-digit',
            second: '2-digit'
        });
    } catch {
        return timeStr;
    }
}

/**
 * HTML转义
 * @param {string} str - 需要转义的字符串
 * @returns {string} 转义后的字符串
 */
function escapeHtml(str) {
    const div = document.createElement('div');
    div.textContent = str;
    return div.innerHTML;
}

/**
 * 切换任务启用/禁用状态
 * @param {string} jobId - 任务ID
 */
export async function toggleJob(jobId) {
    try {
        const response = await fetch(`${API_BASE_URL}/api/schedule/jobs/${jobId}/toggle`, {
            method: 'POST',
            headers: {
                'Content-Type': 'application/json'
            }
        });
        
        const result = await response.json();
        
        if (response.ok) {
            await loadJobs();
        } else {
            alert(`操作失败: ${result.error || '未知错误'}`);
        }
    } catch (error) {
        console.error('切换任务状态失败:', error);
        alert('操作失败，请检查网络连接');
    }
}

/**
 * 编辑任务
 * @param {string} jobId - 任务ID
 */
export async function editJob(jobId) {
    try {
        const response = await fetch(`${API_BASE_URL}/api/schedule/jobs/${jobId}`);
        const result = await response.json();
        
        if (response.ok) {
            const job = result.job;
            
            // 模态框内容 HTML
            const contentHtml = `
                <div style="padding: 20px;">
                    <h3 style="margin: 0 0 20px 0;">编辑定时任务</h3>
                    
                    <div style="margin-bottom: 15px;">
                        <label style="display: block; margin-bottom: 5px;">任务名称</label>
                        <input type="text" class="edit-job-name" value="${escapeHtml(job.name || '')}" style="width: 100%; padding: 8px; box-sizing: border-box;">
                    </div>
                    
                    <div style="margin-bottom: 15px;">
                        <label style="display: block; margin-bottom: 5px;">调度类型</label>
                        <div style="display: flex; gap: 10px;">
                            <label><input type="radio" name="editScheduleType" value="interval" ${job.schedule_type === 'interval' ? 'checked' : ''}> 间隔模式</label>
                            <label><input type="radio" name="editScheduleType" value="cron" ${job.schedule_type === 'cron' ? 'checked' : ''}> Cron模式</label>
                        </div>
                    </div>
                    
                    <div class="edit-interval-settings" style="margin-bottom: 15px; ${job.schedule_type === 'interval' ? '' : 'display: none;'}">
                        <label style="display: block; margin-bottom: 5px;">间隔时间（分钟）</label>
                        <input type="number" class="edit-interval-minutes" min="1" max="1440" value="${job.interval_minutes || 60}" style="width: 100%; padding: 8px; box-sizing: border-box;">
                    </div>
                    
                    <div class="edit-cron-settings" style="margin-bottom: 15px; ${job.schedule_type === 'cron' ? '' : 'display: none;'}">
                        <label style="display: block; margin-bottom: 5px;">Cron表达式</label>
                        <input type="text" class="edit-cron-expression" value="${escapeHtml(job.cron_expression || '')}" placeholder="例如：0 9 * * *" style="width: 100%; padding: 8px; box-sizing: border-box;">
                    </div>
                    
                    <div style="margin-bottom: 15px;">
                        <label style="display: block; margin-bottom: 5px;">发布平台</label>
                        <div style="display: flex; gap: 15px; flex-wrap: wrap;">
                            <label><input type="checkbox" class="edit-platform" value="tiktok" ${job.platforms.includes('tiktok') ? 'checked' : ''}> 🎵 TikTok</label>
                            <label><input type="checkbox" class="edit-platform" value="instagram" ${job.platforms.includes('instagram') ? 'checked' : ''}> 📷 Instagram</label>
                            <label><input type="checkbox" class="edit-platform" value="facebook" ${job.platforms.includes('facebook') ? 'checked' : ''}> 📘 Facebook</label>
                        </div>
                    </div>
                    
                    <div style="margin-bottom: 15px;">
                        <label style="display: block; margin-bottom: 5px;">每次发布数量</label>
                        <input type="number" class="edit-count-per-run" min="1" max="10" value="${job.count_per_run || 1}" style="width: 100%; padding: 8px; box-sizing: border-box;">
                    </div>
                    
                    <div style="margin-bottom: 15px;">
                        <label style="display: block; margin-bottom: 5px;">发布上限（可选）</label>
                        <input type="number" class="edit-max-publish-count" min="1" placeholder="达到此数量后自动停止" value="${job.max_publish_count || ''}" style="width: 100%; padding: 8px; box-sizing: border-box;">
                    </div>
                    
                    <div style="margin-bottom: 15px;">
                        <label><input type="checkbox" class="edit-enabled" ${job.enabled ? 'checked' : ''}> 启用任务</label>
                    </div>
                    
                    <div style="display: flex; gap: 10px;">
                        <button class="btn btn-primary save-edit-btn" style="flex: 1;">保存</button>
                        <button class="btn btn-secondary cancel-edit-btn" style="flex: 1;">取消</button>
                    </div>
                </div>
            `;
            
            // 创建模态框
            const { content, close } = window.appUtils.createModal(contentHtml, 500);
            
            // 获取元素引用
            const saveBtn = content.querySelector('.save-edit-btn');
            const cancelBtn = content.querySelector('.cancel-edit-btn');
            const nameInput = content.querySelector('.edit-job-name');
            const intervalMinutesInput = content.querySelector('.edit-interval-minutes');
            const cronExpressionInput = content.querySelector('.edit-cron-expression');
            const countPerRunInput = content.querySelector('.edit-count-per-run');
            const maxPublishCountInput = content.querySelector('.edit-max-publish-count');
            const enabledCheckbox = content.querySelector('.edit-enabled');
            
            // 调度类型切换
            const scheduleTypeRadios = content.querySelectorAll('input[name="editScheduleType"]');
            scheduleTypeRadios.forEach(radio => {
                radio.addEventListener('change', () => {
                    content.querySelector('.edit-interval-settings').style.display = 
                        radio.value === 'interval' ? 'block' : 'none';
                    content.querySelector('.edit-cron-settings').style.display = 
                        radio.value === 'cron' ? 'block' : 'none';
                });
            });
            
            // 保存按钮点击事件
            saveBtn.addEventListener('click', async () => {
                const scheduleType = content.querySelector('input[name="editScheduleType"]:checked').value;
                const selectedPlatforms = Array.from(content.querySelectorAll('.edit-platform:checked')).map(el => el.value);
                
                if (!nameInput.value.trim()) {
                    alert('请输入任务名称');
                    return;
                }
                
                if (scheduleType === 'cron' && !cronExpressionInput.value.trim()) {
                    alert('Cron模式需要输入Cron表达式');
                    return;
                }
                
                if (selectedPlatforms.length === 0) {
                    alert('请至少选择一个发布平台');
                    return;
                }
                
                // 按钮加载状态
                const originalText = saveBtn.textContent;
                saveBtn.disabled = true;
                saveBtn.textContent = '保存中...';
                
                try {
                    const data = {
                        name: nameInput.value.trim(),
                        schedule_type: scheduleType,
                        interval_minutes: scheduleType === 'interval' ? parseInt(intervalMinutesInput.value) || 60 : undefined,
                        cron_expression: scheduleType === 'cron' ? cronExpressionInput.value.trim() : undefined,
                        platforms: selectedPlatforms,
                        count_per_run: parseInt(countPerRunInput.value) || 1,
                        max_publish_count: maxPublishCountInput.value ? parseInt(maxPublishCountInput.value) : undefined,
                        enabled: enabledCheckbox.checked
                    };
                    
                    const response = await fetch(`${API_BASE_URL}/api/schedule/jobs/${jobId}`, {
                        method: 'PUT',
                        headers: { 'Content-Type': 'application/json' },
                        body: JSON.stringify(data)
                    });
                    
                    const result = await response.json();
                    
                    if (response.ok) {
                        loadJobs();
                        close();
                        alert('任务已更新');
                    } else {
                        alert('更新失败: ' + (result.error || '未知错误'));
                    }
                } catch (error) {
                    alert('更新失败: ' + error.message);
                } finally {
                    // 恢复按钮状态
                    saveBtn.disabled = false;
                    saveBtn.textContent = originalText;
                }
            });
            
            // 取消按钮点击事件
            cancelBtn.addEventListener('click', close);
            
        } else {
            alert(`获取任务失败: ${result.error || '未知错误'}`);
        }
    } catch (error) {
        console.error('编辑任务失败:', error);
        alert('操作失败，请检查网络连接');
    }
}

/**
 * 删除任务
 * @param {string} jobId - 任务ID
 */
export async function deleteJob(jobId) {
    if (!confirm('确定要删除这个定时任务吗？')) {
        return;
    }
    
    try {
        const response = await fetch(`${API_BASE_URL}/api/schedule/jobs/${jobId}`, {
            method: 'DELETE'
        });
        
        const result = await response.json();
        
        if (response.ok) {
            await loadJobs();
        } else {
            alert(`删除失败: ${result.error || '未知错误'}`);
        }
    } catch (error) {
        console.error('删除任务失败:', error);
        alert('删除失败，请检查网络连接');
    }
}

/**
 * 立即执行发布测试
 */
export async function runNow() {
    const platforms = Array.from(document.querySelectorAll('input[name="testPlatform"]:checked')).map(el => el.value);
    const count = parseInt(document.getElementById('testCount').value) || 1;
    
    if (platforms.length === 0) {
        alert('请至少选择一个发布平台');
        return;
    }
    
    if (!confirm(`确定要立即发布 ${count} 个产品到 ${platforms.join(', ')} 吗？`)) {
        return;
    }
    
    const button = document.getElementById('runNowBtn');
    const originalText = button.textContent;
    button.textContent = '⏳ 执行中...';
    button.disabled = true;
    
    try {
        const response = await fetch(`${API_BASE_URL}/api/schedule/run-now`, {
            method: 'POST',
            headers: {
                'Content-Type': 'application/json'
            },
            body: JSON.stringify({ platforms, count })
        });
        
        const result = await response.json();
        
        if (response.ok) {
            alert(result.message || '任务已启动，请到日志中查看执行结果');
        } else {
            alert(`执行失败: ${result.error || '未知错误'}`);
        }
    } catch (error) {
        console.error('执行测试发布失败:', error);
        alert('执行失败，请检查网络连接');
    } finally {
        button.textContent = originalText;
        button.disabled = false;
    }
}