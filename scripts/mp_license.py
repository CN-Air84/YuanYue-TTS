# coding=utf-8
from PyQt5.QtWidgets import (
    QDialog, QVBoxLayout, QTabWidget, QTextEdit, QHBoxLayout, QPushButton
)
from PyQt5.QtGui import QFont

try:
    from misc_func import SettingsManager
    SETTINGS_AVAILABLE = True
except ImportError:
    SETTINGS_AVAILABLE = False

class LicenseDialog(QDialog):
    """许可协议对话框 - 显示软件许可协议"""
    
    def __init__(self, parent=None):
        """
        初始化许可协议对话框
        
        Args:
            parent: 父窗口
        """
        super().__init__(parent)
        self.parent_window = parent
        self.setWindowTitle("许可协议")
        self.resize(900, 700)
        
        if SETTINGS_AVAILABLE:
            self.global_font = SettingsManager().get_Custom_value('global_font', '微软雅黑')
            self.min_font_size = int(SettingsManager().get_Custom_value('min_font_size', '22'))
            self.max_font_size = int(SettingsManager().get_Custom_value('max_font_size', '42'))
        else:
            self.global_font = '微软雅黑'
            self.min_font_size = 22
            self.max_font_size = 42
        
        background_color = SettingsManager().get_Custom_value('background_color', '#E5E8EF') if SETTINGS_AVAILABLE else "#E5E8EF"
        self.setStyleSheet(f"""
            QDialog {{background-color: {background_color};}}
            QPushButton {{
                font-family: "{self.global_font}"; background-color: white; color: black;
                border: 2px solid gray; border-radius: 5px; font-weight: bold; padding: 5px;
            }}
            QPushButton:hover {{background-color: #f0f0f0;}}
            QLabel {{font-family: "{self.global_font}";}}
            QTabWidget::pane {{
                border: 2px solid gray;
                border-radius: 5px;
                background-color: white;
            }}
            QTabBar::tab {{
                background-color: #e0e0e0;
                color: black;
                padding: 8px 16px;
                margin-right: 2px;
                border-top-left-radius: 5px;
                border-top-right-radius: 5px;
            }}
            QTabBar::tab:selected {{
                background-color: white;
                font-weight: bold;
            }}
        """)
        
        self._init_ui()
        self._update_fonts()
    
    def _init_ui(self):
        """初始化用户界面"""
        layout = QVBoxLayout()
        layout.setSpacing(10)
        layout.setContentsMargins(30, 30, 30, 30)
        
        self.tab_widget = QTabWidget()
        
        tab1_text = (
            '''
            本程序基于Apache2.0协议开源，同时使用了基于MIT协议开源的tchMaterial_parser项目相关代码。
            以下为Apache2.0协议原文。来自https://httpd.apache.org/docs/current/zh-cn/license.html。
            Apache License
Version 2.0, January 2004
http://www.apache.org/licenses/

TERMS AND CONDITIONS FOR USE, REPRODUCTION, AND DISTRIBUTION

Definitions
"License" shall mean the terms and conditions for use, reproduction, and distribution as defined by Sections 1 through 9 of this document.

"Licensor" shall mean the copyright owner or entity authorized by the copyright owner that is granting the License.

"Legal Entity" shall mean the union of the acting entity and all other entities that control, are controlled by, or are under common control with that entity. For the purposes of this definition, "control" means (i) the power, direct or indirect, to cause the direction or management of such entity, whether by contract or otherwise, or (ii) ownership of fifty percent (50%) or more of the outstanding shares, or (iii) beneficial ownership of such entity.

"You" (or "Your") shall mean an individual or Legal Entity exercising permissions granted by this License.

"Source" form shall mean the preferred form for making modifications, including but not limited to software source code, documentation source, and configuration files.

"Object" form shall mean any form resulting from mechanical transformation or translation of a Source form, including but not limited to compiled object code, generated documentation, and conversions to other media types.

"Work" shall mean the work of authorship, whether in Source or Object form, made available under the License, as indicated by a copyright notice that is included in or attached to the work (an example is provided in the Appendix below).

"Derivative Works" shall mean any work, whether in Source or Object form, that is based on (or derived from) the Work and for which the editorial revisions, annotations, elaborations, or other modifications represent, as a whole, an original work of authorship. For the purposes of this License, Derivative Works shall not include works that remain separable from, or merely link (or bind by name) to the interfaces of, the Work and Derivative Works thereof.

"Contribution" shall mean any work of authorship, including the original version of the Work and any modifications or additions to that Work or Derivative Works thereof, that is intentionally submitted to Licensor for inclusion in the Work by the copyright owner or by an individual or Legal Entity authorized to submit on behalf of the copyright owner. For the purposes of this definition, "submitted" means any form of electronic, verbal, or written communication sent to the Licensor or its representatives, including but not limited to communication on electronic mailing lists, source code control systems, and issue tracking systems that are managed by, or on behalf of, the Licensor for the purpose of discussing and improving the Work, but excluding communication that is conspicuously marked or otherwise designated in writing by the copyright owner as "Not a Contribution."

"Contributor" shall mean Licensor and any individual or Legal Entity on behalf of whom a Contribution has been received by Licensor and subsequently incorporated within the Work.

Grant of Copyright License. Subject to the terms and conditions of this License, each Contributor hereby grants to You a perpetual, worldwide, non-exclusive, no-charge, royalty-free, irrevocable copyright license to reproduce, prepare Derivative Works of, publicly display, publicly perform, sublicense, and distribute the Work and such Derivative Works in Source or Object form.
Grant of Patent License. Subject to the terms and conditions of this License, each Contributor hereby grants to You a perpetual, worldwide, non-exclusive, no-charge, royalty-free, irrevocable (except as stated in this section) patent license to make, have made, use, offer to sell, sell, import, and otherwise transfer the Work, where such license applies only to those patent claims licensable by such Contributor that are necessarily infringed by their Contribution(s) alone or by combination of their Contribution(s) with the Work to which such Contribution(s) was submitted. If You institute patent litigation against any entity (including a cross-claim or counterclaim in a lawsuit) alleging that the Work or a Contribution incorporated within the Work constitutes direct or contributory patent infringement, then any patent licenses granted to You under this License for that Work shall terminate as of the date such litigation is filed.
Redistribution. You may reproduce and distribute copies of the Work or Derivative Works thereof in any medium, with or without modifications, and in Source or Object form, provided that You meet the following conditions:
You must give any other recipients of the Work or Derivative Works a copy of this License; and
You must cause any modified files to carry prominent notices stating that You changed the files; and
You must retain, in the Source form of any Derivative Works that You distribute, all copyright, patent, trademark, and attribution notices from the Source form of the Work, excluding those notices that do not pertain to any part of the Derivative Works; and
If the Work includes a "NOTICE" text file as part of its distribution, then any Derivative Works that You distribute must include a readable copy of the attribution notices contained within such NOTICE file, excluding those notices that do not pertain to any part of the Derivative Works, in at least one of the following places: within a NOTICE text file distributed as part of the Derivative Works; within the Source form or documentation, if provided along with the Derivative Works; or, within a display generated by the Derivative Works, if and wherever such third-party notices normally appear. The contents of the NOTICE file are for informational purposes only and do not modify the License. You may add Your own attribution notices within Derivative Works that You distribute, alongside or as an addendum to the NOTICE text from the Work, provided that such additional attribution notices cannot be construed as modifying the License.
You may add Your own copyright statement to Your modifications and may provide additional or different license terms and conditions for use, reproduction, or distribution of Your modifications, or for any such Derivative Works as a whole, provided Your use, reproduction, and distribution of the Work otherwise complies with the conditions stated in this License.

Submission of Contributions. Unless You explicitly state otherwise, any Contribution intentionally submitted for inclusion in the Work by You to the Licensor shall be under the terms and conditions of this License, without any additional terms or conditions. Notwithstanding the above, nothing herein shall supersede or modify the terms of any separate license agreement you may have executed with Licensor regarding such Contributions.
Trademarks. This License does not grant permission to use the trade names, trademarks, service marks, or product names of the Licensor, except as required for reasonable and customary use in describing the origin of the Work and reproducing the content of the NOTICE file.
Disclaimer of Warranty. Unless required by applicable law or agreed to in writing, Licensor provides the Work (and each Contributor provides its Contributions) on an "AS IS" BASIS, WITHOUT WARRANTIES OR CONDITIONS OF ANY KIND, either express or implied, including, without limitation, any warranties or conditions of TITLE, NON-INFRINGEMENT, MERCHANTABILITY, or FITNESS FOR A PARTICULAR PURPOSE. You are solely responsible for determining the appropriateness of using or redistributing the Work and assume any risks associated with Your exercise of permissions under this License.
Limitation of Liability. In no event and under no legal theory, whether in tort (including negligence), contract, or otherwise, unless required by applicable law (such as deliberate and grossly negligent acts) or agreed to in writing, shall any Contributor be liable to You for damages, including any direct, indirect, special, incidental, or consequential damages of any character arising as a result of this License or out of the use or inability to use the Work (including but not limited to damages for loss of goodwill, work stoppage, computer failure or malfunction, or any and all other commercial damages or losses), even if such Contributor has been advised of the possibility of such damages.
Accepting Warranty or Additional Liability. While redistributing the Work or Derivative Works thereof, You may choose to offer, and charge a fee for, acceptance of support, warranty, indemnity, or other liability obligations and/or rights consistent with this License. However, in accepting such obligations, You may act only on Your own behalf and on Your sole responsibility, not on behalf of any other Contributor, and only if You agree to indemnify, defend, and hold each Contributor harmless for any liability incurred by, or claims asserted against, such Contributor by reason of your accepting any such warranty or additional liability.

            '''
        )
        
        tab2_text = (
            '''Apache 许可证 2.0（中文翻译 由豆包翻译）
Apache 许可证
版本 2.0，2004 年 1 月
http://www.apache.org/licenses/
使用、复制和分发的条款与条件
定义
“许可证” 指本文件第 1 至第 9 节规定的关于使用、复制和分发的条款与条件。
“许可人” 指授予本许可证的版权所有者 or 经版权所有者授权的实体。
“法律实体” 指行为实体及其所有控制、被控制或处于共同控制下的其他实体。就本定义而言，“控制” 指：(i) 直接或间接指导或管理该实体的权力（无论是否通过合同）；(ii) 拥有该实体 50% 及以上已发行股份；或 (iii) 该实体的受益所有权。
“您” 指行使本许可证授予权限的个人或法律实体。
“源形式” 指进行修改的首选形式，包括但不限于软件源代码、文档源文件和配置文件。
“目标形式” 指源形式经机械转换或翻译后的任何形式，包括但不限于编译的目标代码、生成的文档及转换为其他媒体类型的文件。
“作品” 指依据本许可证提供的、包含版权声明（示例见附录）的原创成果，可为源形式或目标形式。
“衍生作品” 指基于原作品创作的、整体构成原创成果的任何源形式或目标形式作品，包括编辑修订、注释、阐述或其他修改。本许可证下，衍生作品不包括与原作品及衍生作品的接口保持可分离状态，或仅通过名称链接的作品。
“贡献” 指版权所有者或其授权的个人 / 法律实体有意提交给许可人以纳入作品的任何原创成果，包括作品的原始版本及对其的修改或补充。“提交” 指发送至许可人或其代表的任何电子、口头或书面沟通（如邮件列表、代码控制系统、问题追踪系统中的沟通），但不包括版权所有者明确标注为 “非贡献” 的内容。
“贡献者” 指许可人及所有提交的贡献被许可人接收并纳入作品的个人或法律实体。
版权许可授予
依据本许可证条款，每位贡献者授予您永久性、全球性、非排他性、免费、免版税、不可撤销的版权许可，允许您以源形式或目标形式复制、创作衍生作品、公开展示、公开表演、再许可和分发原作品及衍生作品。
专利许可授予
依据本许可证条款，每位贡献者授予您永久性、全球性、非排他性、免费、免版税、不可撤销（本节另有规定除外）的专利许可，允许您制造、使用、要约出售、销售、进口并以其他方式转让作品。该许可仅适用于贡献者可许可的、其贡献单独或与所提交作品结合必然侵权的专利权利要求。若您对任何实体提起专利诉讼（包括诉讼中的交叉索赔或反诉），指控作品或其中的贡献构成直接或辅助专利侵权，则本许可证授予您的相关专利许可自诉讼提起之日起终止。
再分发
您可复制并分发作品或其衍生作品的副本（可修改，源形式或目标形式），但需满足以下条件：
(a) 向其他接收者提供本许可证副本；
(b) 对修改过的文件标注显著声明，说明您已更改该文件；
(c) 在分发的衍生作品源形式中，保留原作品源形式中的所有版权、专利、商标和归属声明（不涉及衍生作品部分的除外）；
(d) 若作品包含 “NOTICE” 文本文件，分发的衍生作品需包含该文件中的归属声明（不涉及衍生作品部分的除外）。您可在衍生作品中添加自己的归属声明（可与原 NOTICE 文件内容并列或作为补充），且仅可使用原归属声明标注原作者，不得暗示其认可您或您对作品的使用。
贡献的提交
除非您明确声明，您提交给许可人的任何贡献均受本许可证条款约束，无额外条款。但本规定不取代或修改您与许可人就贡献另行签订的许可协议。
商标
本许可证不授予使用许可人商号、商标、服务标志或产品名称的权限，除非描述作品来源或复制 NOTICE 文件内容所需的合理常规使用。
免责声明
除非法律要求或书面约定，许可人提供的作品（及贡献者提供的贡献）均按 “原样” 提供，不承担任何明示或暗示的担保责任，包括但不限于所有权、非侵权、适销性和特定用途适用性的担保。您需自行判断使用或再分发作品的适当性，并承担相关风险。
责任限制
除非法律要求（如故意或重大过失行为）或书面约定，任何贡献者在任何法律理论下（侵权、合同等）均不对您因本许可证或使用 / 无法使用作品导致的任何直接、间接、特殊、偶然或后果性损害承担责任，即使已被告知此类损害的可能性。
责任担保或额外责任
再分发作品或其衍生作品时，您可选择提供支持、担保、赔偿或其他责任义务 / 权利并收取费用，但需自行承担责任，不得代表其他贡献者，且需赔偿、辩护并使各贡献者免受因您接受此类义务而产生的任何责任或索赔。
条款与条件结束
附录：如何将 Apache 许可证应用于您的作品
如需将 Apache 许可证应用于您的作品，请附上以下标准声明，替换括号中的标识信息（不含括号）：
版权所有 [年份] [版权所有者]
依据 Apache 许可证 2.0 版（以下简称 “许可证”）授权；
除非遵守许可证，否则不得使用本文件。
您可从 http://www.apache.org/licenses/LICENSE-2.0 获取许可证副本。
除非法律要求或书面约定，根据许可证分发的软件按 “原样” 提供，
不附带任何明示或暗示的担保或条件。
有关许可证下的权限和限制，请参见许可证具体条款。
'''
        )
        
        tab3_text = (
            '''MIT 许可证 来自https://github.com/happycola233/tchMaterial-parser/tree/main?tab=MIT-1-ov-file
            
            MIT License  麻省理工学院许可

Copyright (c) 2026 肥宅水水呀

Permission is hereby granted, free of charge, to any person obtaining a copy
of this software and associated documentation files (the "Software"), to deal
in the Software without restriction, including without limitation the rights
to use, copy, modify, merge, publish, distribute, sublicense, and/or sell
copies of the Software, and to permit persons to whom the Software is
furnished to do so, subject to the following conditions:
特此免费授权任何人获得本软件及相关文档文件（“软件”）的副本，不受限制地使用该软件，包括但不限于使用、复制、修改、合并、发布、分发、再许可和/或销售软件副本的权利，并允许软件提供者这样做， 但须满足以下条件：

The above copyright notice and this permission notice shall be included in all
copies or substantial portions of the Software.
上述版权声明及本许可声明应包含在软件的所有副本或大部分内容中。

THE SOFTWARE IS PROVIDED "AS IS", WITHOUT WARRANTY OF ANY KIND, EXPRESS OR
IMPLIED, INCLUDING BUT NOT LIMITED TO THE WARRANTIES OF MERCHANTABILITY,
FITNESS FOR A PARTICULAR PURPOSE AND NONINFRINGEMENT. IN NO EVENT SHALL THE
AUTHORS OR COPYRIGHT HOLDERS BE LIABLE FOR ANY CLAIM, DAMAGES OR OTHER
LIABILITY, WHETHER IN AN ACTION OF CONTRACT, TORT OR OTHERWISE, ARISING FROM,
OUT OF OR IN CONNECTION WITH THE SOFTWARE OR THE USE OR OTHER DEALINGS IN THE
SOFTWARE.

软件以“现状”提供，不提供任何明示或暗示的保证，包括但不限于可销性、特定用途适用性和非侵权等保证。无论如何，作者或版权持有人对因软件或软件使用或其他交易产生的、涉及合同、侵权或其他诉讼的索赔、损害或其他责任均不承担责任。'''
        )
        
        tab1 = self._create_tab(tab1_text, "  Apache2.0许可证 原版"  )
        tab2 = self._create_tab(tab2_text, "  Apache2.0新款裤子 译文  ")
        tab3 = self._create_tab(tab3_text, "  MIT 许可证  ")
        
        self.tab_widget.addTab(tab1, "  Apache2.0许可证 原版  ")
        self.tab_widget.addTab(tab2, "  Apache2.0许可证 译文  ")
        self.tab_widget.addTab(tab3, "  MIT 许可证  ")
        
        layout.addWidget(self.tab_widget)
        
        button_layout = QHBoxLayout()
        button_layout.addStretch()
        
        self.close_button = QPushButton("关闭")
        self.close_button.clicked.connect(self.accept)
        button_layout.addWidget(self.close_button)
        
        layout.addLayout(button_layout)
        self.setLayout(layout)
    
    def _create_tab(self, text, title):
        """
        创建标签页
        
        Args:
            text (str): 标签页文本内容
            title (str): 标签页标题
            
        Returns:
            QTextEdit: 文本编辑控件
        """
        text_edit = QTextEdit()
        text_edit.setPlainText(text)
        text_edit.setReadOnly(True)
        text_edit.setStyleSheet(f"""
            QTextEdit {{
                background-color: white;
                color: black;
                border: none;
                border-radius: 5px;
                padding: 15px;
                font-family: "{self.global_font}";
                font-size: 11px;
            }}
        """)
        return text_edit
    
    def _update_fonts(self):
        """更新界面字体大小"""
        current_width = self.width()
        current_height = self.height()
        
        DEFAULT_WIDTH = 900
        DEFAULT_HEIGHT = 700
        MIN_FONT_SIZE = self.min_font_size
        MAX_FONT_SIZE = self.max_font_size
        
        width_ratio = current_width / DEFAULT_WIDTH
        height_ratio = current_height / DEFAULT_HEIGHT
        ratio = (width_ratio + height_ratio) / 2
        
        base_font_size = (MIN_FONT_SIZE + 
                         (MAX_FONT_SIZE - MIN_FONT_SIZE) * (ratio - 1))
        base_font_size = max(MIN_FONT_SIZE, min(MAX_FONT_SIZE, base_font_size))
        
        base_font_size = int(base_font_size)
        button_font_size = int(base_font_size * 0.5)
        
        button_font = QFont(self.global_font, button_font_size)
        self.close_button.setFont(button_font)
    
    def resizeEvent(self, event):
        """处理窗口大小变化事件"""
        self._update_fonts()
        super().resizeEvent(event)
