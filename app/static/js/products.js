/**
 * @fileoverview 产品管理模块 - 提供产品的增删改查功能
 * @module products
 * @description 该模块负责管理产品列表，包括加载、添加、编辑和删除产品的功能
 */

import { showStatus, createModal } from './utils.js';

/**
 * 当前产品列表数据
 * @type {Array<Object>}
 */
let products = [];

/**
 * 从后端加载产品列表
 * @async
 * @description 调用 API 获取产品数据并更新本地状态和 UI
 * @returns {Promise<void>}
 */
async function loadProducts() {
    try {
        const response = await fetch('/api/products');
        const data = await response.json();
        products = data.products;
        renderProductList();
    } catch (error) {
        showStatus('加载产品列表失败: ' + error.message, 'error');
    }
}

/**
 * 渲染产品列表到页面
 * @description 根据当前 products 数据生成 HTML 并插入到页面
 */
function renderProductList() {
    const container = document.getElementById('productList');
    
    // 处理空列表情况
    if (products.length === 0) {
        container.innerHTML = '<p style="color: #666;">暂无产品，请添加</p>';
        return;
    }
    
    // 生成产品列表 HTML
    container.innerHTML = products.map((product, index) => `
        <div class="product-item" style="border: 1px solid #eee; border-radius: 8px; margin-bottom: 12px; overflow: hidden;">
            <div style="padding: 15px;">
                <div style="display: flex; align-items: center; justify-content: space-between; margin-bottom: 8px;">
                    <span style="font-weight: bold; font-size: 1.1rem;">${index + 1}. ${product.name}</span>
                    <div style="display: flex; gap: 10px;">
                        <button class="btn btn-primary btn-sm" onclick="window.appProducts.editProduct(${index})">编辑</button>
                        <button class="btn btn-danger btn-sm" onclick="window.appProducts.deleteProduct(${index})">删除</button>
                    </div>
                </div>
                ${product.description ? 
                    `<p style="margin: 0; color: #666; font-size: 0.9rem; padding-left: 10px; border-left: 3px solid #ddd;">${product.description}</p>` : 
                    '<p style="margin: 0; color: #999; font-size: 0.9rem; padding-left: 10px; font-style: italic;">暂无描述</p>'}
            </div>
        </div>
    `).join('');
}

/**
 * 添加新产品
 * @async
 * @description 从表单获取产品信息，调用 API 添加产品
 * @returns {Promise<void>}
 */
async function addProduct() {
    const nameInput = document.getElementById('newProductNameInput');
    const descInput = document.getElementById('newProductDescription');
    const productName = nameInput.value.trim();
    const description = descInput.value.trim();
    
    // 验证产品名称必填
    if (!productName) {
        showStatus('请输入产品名称', 'error');
        return;
    }
    
    try {
        const response = await fetch('/api/products', {
            method: 'POST',
            headers: { 'Content-Type': 'application/json' },
            body: JSON.stringify({ 
                product_name: productName,
                description: description
            })
        });
        
        const data = await response.json();
        
        if (data.error) {
            showStatus('添加失败: ' + data.error, 'error');
            return;
        }
        
        // 更新产品列表并清空表单
        products = data.products;
        nameInput.value = '';
        descInput.value = '';
        renderProductList();
        showStatus('产品添加成功！', 'success');
    } catch (error) {
        showStatus('添加失败: ' + error.message, 'error');
    }
}

/**
 * 编辑产品
 * @async
 * @param {number} index - 要编辑的产品在列表中的索引
 * @description 显示编辑模态框，保存修改后更新产品列表
 * @returns {Promise<void>}
 */
async function editProduct(index) {
    const product = products[index];
    
    // 模态框内容 HTML
    const contentHtml = `
        <div style="padding: 20px;">
            <h3 style="margin: 0 0 15px 0;">编辑产品</h3>
            <div style="margin-bottom: 15px;">
                <label style="display: block; margin-bottom: 5px;">产品名称</label>
                <input type="text" class="edit-product-name" value="${product.name}" style="width: 100%; padding: 8px; box-sizing: border-box;">
            </div>
            <div style="margin-bottom: 15px;">
                <label style="display: block; margin-bottom: 5px;">产品描述</label>
                <textarea class="edit-product-desc" rows="3" style="width: 100%; padding: 8px; box-sizing: border-box;">${product.description || ''}</textarea>
            </div>
            <div style="display: flex; gap: 10px;">
                <button class="btn btn-primary save-edit-btn" style="flex: 1;">保存</button>
                <button class="btn btn-secondary cancel-edit-btn" style="flex: 1;">取消</button>
            </div>
        </div>
    `;
    
    // 创建模态框
    const { content, close } = createModal(contentHtml);
    
    // 获取元素引用
    const saveBtn = content.querySelector('.save-edit-btn');
    const cancelBtn = content.querySelector('.cancel-edit-btn');
    const nameInput = content.querySelector('.edit-product-name');
    const descInput = content.querySelector('.edit-product-desc');
    
    // 保存按钮点击事件
    saveBtn.addEventListener('click', async () => {
        const newName = nameInput.value.trim();
        const newDesc = descInput.value.trim();
        
        if (!newName) {
            showStatus('请输入产品名称', 'error');
            return;
        }
        
        // 按钮加载状态
        const originalText = saveBtn.textContent;
        saveBtn.disabled = true;
        saveBtn.textContent = '保存中...';
        
        try {
            const response = await fetch(`/api/products/${index}`, {
                method: 'PUT',
                headers: { 'Content-Type': 'application/json' },
                body: JSON.stringify({ 
                    product_name: newName,
                    description: newDesc
                })
            });
            
            const data = await response.json();
            
            if (data.error) {
                showStatus('修改失败: ' + data.error, 'error');
                return;
            }
            
            products = data.products;
            renderProductList();
            close();
            showStatus('产品已修改', 'success');
        } catch (error) {
            showStatus('修改失败: ' + error.message, 'error');
        } finally {
            // 恢复按钮状态
            saveBtn.disabled = false;
            saveBtn.textContent = originalText;
        }
    });
    
    // 取消按钮点击事件
    cancelBtn.addEventListener('click', close);
}

/**
 * 删除产品
 * @async
 * @param {number} index - 要删除的产品在列表中的索引
 * @description 显示确认对话框，确认后调用 API 删除产品
 * @returns {Promise<void>}
 */
async function deleteProduct(index) {
    const productName = products[index].name;
    
    // 确认删除
    if (!confirm(`确定要删除产品 "${productName}" 吗？`)) {
        return;
    }
    
    try {
        const response = await fetch(`/api/products/${index}`, {
            method: 'DELETE'
        });
        
        const data = await response.json();
        
        if (data.error) {
            showStatus('删除失败: ' + data.error, 'error');
            return;
        }
        
        products = data.products;
        renderProductList();
        showStatus(`产品 "${data.deleted.name}" 已删除`, 'success');
    } catch (error) {
        showStatus('删除失败: ' + error.message, 'error');
    }
}

export {
    loadProducts,
    addProduct,
    editProduct,
    deleteProduct
};
