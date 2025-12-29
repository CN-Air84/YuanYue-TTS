## 0.检查工作

首先，按下Win+R键，呼出“运行”窗口，输入Winver。

检查窗口内"Microsoft Windows"下一行显示的“版本”是多少。

如果版本号前两位大于18，或版本号为1809，则可以使用第一种方法。

否则请使用第二种方法。

<img width="1664" height="809" alt="image" src="https://github.com/user-attachments/assets/24a767ca-eda7-4c13-a070-37202fd4890b" />

<img width="839" height="739" alt="image" src="https://github.com/user-attachments/assets/3707bd49-4b21-4263-bf96-d29558d0089c" />


## 1. 第一种方法：Winget安装法

还是Win+R，这次输入cmd。

然后在新弹出的命令提示符窗口输入以下指令：
```
winget install ffmpeg

```

等他提示安装完成即可。

<img width="624" height="319" alt="image" src="https://github.com/user-attachments/assets/5197bb1b-ddf0-4808-9911-3a19da29f8a8" />


<img width="1730" height="924" alt="image" src="https://github.com/user-attachments/assets/c84bd164-4a62-4a10-9dff-3b8eaf3a167d" />


## 2. 第二种方法：手动安装

步骤1：[下载ffmpeg的安装包](https://www.gyan.dev/ffmpeg/builds/ffmpeg-git-essentials.7z)

#### 步骤 2：解压

下载完成后，右键点击压缩包进行解压。

为了方便管理，建议将解压后的文件夹重命名为简单的名字，例如 ffmpeg。

将这个文件夹移动到一个固定位置，最好不要放在桌面或临时文件夹。推荐路径：

D:\Tools\ffmpeg

#### 步骤 3：配置环境变量

这是让 ffmpeg 在任何地方都能被命令行识别的关键步骤。

在 Windows 搜索栏输入“编辑系统环境变量”并打开。

点击右下角的“环境变量”按钮。

在“用户变量”或“系统变量”（推荐用户变量）区域，找到名为 Path 的变量，选中它并点击“编辑”。

点击右侧的“新建”。

输入你刚才解压的 FFmpeg 文件夹内的 bin 目录路径。例如：

D:\Tools\ffmpeg\bin

点击“确定”保存所有设置。

#### 步骤 4：验证安装

按 Win + R，输入 cmd 并回车，打开命令提示符。

输入以下命令并回车：
···

    ffmpeg -version
···

如果出现了一堆版本信息（如 ffmpeg version N-xxx…），说明安装成功！

如果提示“不是内部或外部命令”，说明环境变量配置有问题，请检查路径是否正确，或者重启电脑后再试。
