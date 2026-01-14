const { app, BrowserWindow } = require('electron');
const fs = require('fs');
const path = require('path');

let mainWindow;

// 检查是否在CLI模式下运行
const isCliMode = process.argv.includes('--cli') || 
                   process.argv.includes('-c');

// 解析命令行参数
function parseArgs() {
  const args = process.argv.slice(2);
  const options = {
    outputFile: 'links.txt',
    url: 'https://basic.smartedu.cn/tchMaterial'
  };
  
  for (let i = 0; i < args.length; i++) {
    if (args[i] === '--output' || args[i] === '-o') {
      options.outputFile = args[i + 1] || 'links.txt';
      i++;
    }
    if (args[i] === '--url' || args[i] === '-u') {
      options.url = args[i + 1] || options.url;
      i++;
    }
  }
  
  return options;
}

const options = parseArgs();

// 格式化时间戳 [YY-MM-DD hh-mm-ss]
function formatTimestamp() {
  const now = new Date();
  
  const yy = String(now.getFullYear()).slice(-2);
  const mm = String(now.getMonth() + 1).padStart(2, '0');
  const dd = String(now.getDate()).padStart(2, '0');
  const hh = String(now.getHours()).padStart(2, '0');
  const min = String(now.getMinutes()).padStart(2, '0');
  const ss = String(now.getSeconds()).padStart(2, '0');
  
  return `[${yy}-${mm}-${dd} ${hh}-${min}-${ss}]`;
}

// 检查URL是否包含目标参数
function checkUrl(url) {
  return url.includes('contentType=assets_document');
}

// 写入链接到文件
function writeLink(url) {
  const outputDir = process.cwd();
  const filePath = path.join(outputDir, options.outputFile);
  
  const line = `${formatTimestamp()}${url}\n`;
  
  try {
    fs.appendFileSync(filePath, line, 'utf8');
    console.log(`Writing Complete: ${filePath}`);
    console.log(`Content: ${line.trim()}`);
  } catch (error) {
    console.error(`Writing Failed: ${error.message}`);
  }
}

// 关闭应用
function quitApp() {
  console.log(' Preparing to Quit');
  
  if (mainWindow) {
    mainWindow.removeAllListeners();
    mainWindow.close();
  }
  
  setTimeout(() => {
    app.quit();
  }, 500);
}

// 创建浏览器窗口
function createWindow() {
  mainWindow = new BrowserWindow({
    width: 1280,
    height: 800,
    title: 'YuanYueTTSPlugin-SmartEduInteract',
    webPreferences: {
      nodeIntegration: false,
      contextIsolation: true,
      sandbox: true
    },
    ...(isCliMode ? { show: true } : {})
  });

  mainWindow.webContents.setWindowOpenHandler(({ url }) => {
    // 阻止新窗口创建
    const action = { action: 'deny' };
    // 在当前窗口加载该 URL
    mainWindow.loadURL(url);
    return action;
  });

  console.log(`Starting: ${options.url}`);
  mainWindow.loadURL(options.url);

  // 监听页面导航完成事件
  mainWindow.webContents.on('did-navigate', (event, url) => {
    console.log(` Go To: ${url}`);
    
    if (checkUrl(url)) {
      console.log('Target On !');
      writeLink(url);
      quitApp();
    }
  });

  // 监听页面内导航（History API 或 点击链接）
  mainWindow.webContents.on('did-navigate-in-page', (event, url) => {
    console.log(`In-Page Navigator: ${url}`);
    
    if (checkUrl(url)) {
      console.log('Target On !');
      writeLink(url);
      quitApp();
    }
  });

  mainWindow.on('closed', () => {
    mainWindow = null;
  });

  if (!isCliMode && process.env.DEBUG) {
    mainWindow.webContents.openDevTools();
  }
}

app.whenReady().then(() => {
  if (isCliMode) {
    console.log('Run in CLI');
    console.log(`Output File: ${path.join(process.cwd(), options.outputFile)}`);
    console.log(` Waiting...\n`);
  } else {
    console.log('Run in GUI');
  }
  
  createWindow();
});

app.on('window-all-closed', () => {
  if (process.platform !== 'darwin') {
    app.quit();
  }
});

app.on('activate', () => {
  if (BrowserWindow.getAllWindows().length === 0) {
    createWindow();
  }
});
