⚠ 阻塞：本环境无微信开发者工具/真机模拟器，小程序详情页新增的「重试」按钮只做了 node --check 语法校验与代码走查，未经实际渲染与点击验证；依赖：可运行微信开发者工具的环境（或真机 + 体验版）。

来源：T02496（FR-UX-302）——该单 verified=false 正是因为这一项无法在本环境实测。

待验证内容（对应 T02496 结果「验证」节的 5 步人工抽查）：
1. apps/miniprogram/pages/detail/detail.wxml 错误态里的 .load-retry-btn 是否正确渲染、样式是否与列表页既有重试按钮一致（样式复用 app.wxss 里 T00599 的类，未新造）。
2. 断网/域名不可达时进入详情页 → 显示错误文案 + 重试按钮；恢复网络点重试 → 回到正常播放界面且错误文案不残留（detail.js 的 loadDetail 成功分支已 setData({error: ""})，需实测确认）。
3. 缺少 id 参数进入详情页时不应出现重试按钮（wx:if="{{episodeId}}" 生效）。
4. 弱网连续点重试不卡死（onRetryLoad 会先 setData({loading:true, error:""}) 再 loadDetail）。
5. 章节语义（isCourse 分支）下重试后上一章/下一章导航与合规提示仍正常。
