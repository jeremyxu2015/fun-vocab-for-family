<#
  VocabMaster 部署脚本
  功能：把本地 Django 项目推送到远程 Linux 服务器
  使用方法：右键用 PowerShell 运行，或在终端执行 .\deploy.ps1
#>

# ========== 询问服务器信息 ==========
Write-Host ""
Write-Host "========================================" -ForegroundColor Cyan
Write-Host "  VocabMaster 部署脚本" -ForegroundColor Cyan
Write-Host "========================================" -ForegroundColor Cyan
Write-Host ""

$ServerIP = Read-Host "请输入服务器 IP 地址"
if (-not $ServerIP) {
    Write-Host "错误：IP 不能为空！" -ForegroundColor Red
    exit 1
}

$ServerUser = Read-Host "请输入用户名（默认 root）"
if (-not $ServerUser) { $ServerUser = "root" }

$ServerPassword = Read-Host "请输入密码" -AsSecureString
$PlainPassword = [Runtime.InteropServices.Marshal]::PtrToStringAuto(
    [Runtime.InteropServices.Marshal]::SecureStringToBSTR($ServerPassword)
)

$ServerPort = Read-Host "请输入 SSH 端口（默认 22）"
if (-not $ServerPort) { $ServerPort = "22" }

$RemotePath = Read-Host "请输入远程部署路径（默认 /www/wwwroot/vocabmaster）"
if (-not $RemotePath) { $RemotePath = "/www/wwwroot/vocabmaster" }

$DjangoPort = Read-Host "请输入 Django 运行端口（默认 8000）"
if (-not $DjangoPort) { $DjangoPort = "8000" }

# ========== 本地路径 ==========
$LocalProject = "D:\学习\work\背单词"

# ========== 检查 sshpass 替代方案 ==========
# Windows 没有 sshpass，用 plink（PuTTY）或者 expect
# 这里用 ssh + StrictHostKeyChecking=no，密码通过 sshpass 传递
# 如果没有 sshpass，先提示用户安装或改用密钥

Write-Host ""
Write-Host "========================================" -ForegroundColor Yellow
Write-Host "  开始部署..." -ForegroundColor Yellow
Write-Host "  服务器: ${ServerUser}@${ServerIP}:${ServerPort}" -ForegroundColor Yellow
Write-Host "  远程路径: $RemotePath" -ForegroundColor Yellow
Write-Host "========================================" -ForegroundColor Yellow
Write-Host ""

# ========== 第1步：准备排除列表 ==========
Write-Host "[1/6] 准备部署文件..." -ForegroundColor Green

$TempDir = "$env:TEMP\vocabmaster_deploy"
if (Test-Path $TempDir) { Remove-Item $TempDir -Recurse -Force }
New-Item -ItemType Directory -Path $TempDir -Force | Out-Null

# 复制项目文件（排除不需要的）
$Excludes = @("venv", "node_modules", "__pycache__", "*.pyc", ".git", "db.sqlite3", "*.log")
Write-Host "  复制项目文件（排除 venv, __pycache__, .git, db.sqlite3）..."

# 用 robocopy 复制（排除目录）
robocopy $LocalProject $TempDir /E /XD venv node_modules __pycache__ .git /XF *.pyc *.log /NFL /NDL /NJH /NJS /NC /NS | Out-Null

Write-Host "  文件准备完成" -ForegroundColor Green

# ========== 第2步：打包 ==========
Write-Host "[2/6] 打包项目..." -ForegroundColor Green

$ZipFile = "$env:TEMP\vocabmaster.tar.gz"
if (Test-Path $ZipFile) { Remove-Item $ZipFile -Force }

# 用 tar 打包（Windows 10+ 自带 tar）
Push-Location $TempDir
tar -czf $ZipFile -C $TempDir .
Pop-Location

$SizeMB = [math]::Round((Get-Item $ZipFile).Length / 1MB, 2)
Write-Host "  打包完成：${SizeMB} MB" -ForegroundColor Green

# ========== 第3步：上传 ==========
Write-Host "[3/6] 上传到服务器..." -ForegroundColor Green

$SSHOptions = "-o StrictHostKeyChecking=no -o UserKnownHostsFile=/dev/null -P $ServerPort"

# 检查是否有 sshpass
$HasSshpass = Get-Command sshpass -ErrorAction SilentlyContinue

if ($HasSshpass) {
    # 用 sshpass
    $env:SSHPASS = $PlainPassword
    Invoke-Expression "sshpass -e scp $SSHOptions `"$ZipFile`" ${ServerUser}@${ServerIP}:/tmp/vocabmaster.tar.gz"
    Invoke-Expression "sshpass -e ssh $SSHOptions -p $ServerPort ${ServerUser}@${ServerIP} 'mkdir -p $RemotePath'"
} else {
    Write-Host ""
    Write-Host "  注意：没有找到 sshpass，将使用交互式 SSH（需要手动输入密码）" -ForegroundColor Yellow
    Write-Host "  密码是: $PlainPassword" -ForegroundColor Yellow
    Write-Host "  如果提示输入密码，请粘贴上面的密码" -ForegroundColor Yellow
    Write-Host ""
    
    # 先创建远程目录
    ssh -o StrictHostKeyChecking=no -o UserKnownHostsFile=NUL -p $ServerPort "${ServerUser}@${ServerIP}" "mkdir -p $RemotePath"
    
    # 上传
    scp -o StrictHostKeyChecking=no -o UserKnownHostsFile=NUL -P $ServerPort "$ZipFile" "${ServerUser}@${ServerIP}:/tmp/vocabmaster.tar.gz"
}

Write-Host "  上传完成" -ForegroundColor Green

# ========== 第4步：远程部署 ==========
Write-Host "[4/6] 远程部署..." -ForegroundColor Green

$DeployScript = @"
set -e
echo '>>> 清理旧文件（保留数据库和虚拟环境）...'
cd $RemotePath

# 备份数据库
if [ -f db.sqlite3 ]; then
    cp db.sqlite3 /tmp/vocabmaster_db_backup.sqlite3
    echo '    数据库已备份到 /tmp'
fi

# 删除旧文件（保留 venv 和 db）
find $RemotePath -mindepth 1 -maxdepth 1 ! -name 'venv' ! -name 'db.sqlite3' -exec rm -rf {} +

echo '>>> 解压新版项目...'
tar -xzf /tmp/vocabmaster.tar.gz -C $RemotePath
rm -f /tmp/vocabmaster.tar.gz

# 恢复数据库（如果新包里没有的话）
if [ ! -f db.sqlite3 ] && [ -f /tmp/vocabmaster_db_backup.sqlite3 ]; then
    cp /tmp/vocabmaster_db_backup.sqlite3 db.sqlite3
    echo '    数据库已恢复'
fi

echo '>>> 安装 Python 环境...'
apt-get update -qq && apt-get install -y -qq python3 python3-venv python3-pip > /dev/null 2>&1 || true

echo '>>> 创建虚拟环境...'
if [ ! -d "$RemotePath/venv" ]; then
    python3 -m venv $RemotePath/venv
fi

echo '>>> 安装依赖...'
$RemotePath/venv/bin/pip install django gunicorn whitenoise -q

echo '>>> 数据库迁移...'
cd $RemotePath
$RemotePath/venv/bin/python manage.py migrate --run-syncdb

echo '>>> 收集静态文件...'
$RemotePath/venv/bin/python manage.py collectstatic --noinput -q 2>/dev/null || true

echo '>>> 部署完成！'
"@

if ($HasSshpass) {
    $env:SSHPASS = $PlainPassword
    $DeployScript | & sshpass -e ssh $SSHOptions -p $ServerPort "${ServerUser}@${ServerIP}" "bash -s"
} else {
    Write-Host "  执行远程部署命令（可能需要输入密码）..." -ForegroundColor Yellow
    $DeployScript | ssh -o StrictHostKeyChecking=no -o UserKnownHostsFile=NUL -p $ServerPort "${ServerUser}@${ServerIP}" "bash -s"
}

# ========== 第5步：配置 systemd 服务 ==========
Write-Host "[5/6] 配置系统服务..." -ForegroundColor Green

$ServiceScript = @"
set -e

# 修改 Django settings: ALLOWED_HOSTS 和 DEBUG
SETTINGS_FILE="$RemotePath/myproject/settings.py"
if [ -f "\$SETTINGS_FILE" ]; then
    # 允许所有主机访问
    sed -i "s/ALLOWED_HOSTS = \[.*\]/ALLOWED_HOSTS = ['*']/" \$SETTINGS_FILE
    # 关闭 DEBUG
    sed -i "s/DEBUG = True/DEBUG = False/" \$SETTINGS_FILE
    echo '>>> Django settings 已更新'
fi

# 创建 systemd 服务
cat > /etc/systemd/system/vocabmaster.service << 'EOF'
[Unit]
Description=VocabMaster Django App
After=network.target

[Service]
User=root
WorkingDirectory=$RemotePath
ExecStart=$RemotePath/venv/bin/gunicorn myproject.wsgi:application --bind 0.0.0.0:$DjangoPort --workers 3 --timeout 120
Restart=always
RestartSec=3
Environment=PYTHONUNBUFFERED=1

[Install]
WantedBy=multi-user.target
EOF

systemctl daemon-reload
systemctl enable vocabmaster
systemctl restart vocabmaster

echo '>>> 服务已启动'
systemctl status vocabmaster --no-pager || true
"@

if ($HasSshpass) {
    $env:SSHPASS = $PlainPassword
    $ServiceScript | & sshpass -e ssh $SSHOptions -p $ServerPort "${ServerUser}@${ServerIP}" "bash -s"
} else {
    $ServiceScript | ssh -o StrictHostKeyChecking=no -o UserKnownHostsFile=NUL -p $ServerPort "${ServerUser}@${ServerIP}" "bash -s"
}

# ========== 第6步：配置防火墙 ==========
Write-Host "[6/6] 开放端口..." -ForegroundColor Green

$FirewallScript = @"
# 尝试用 ufw
if command -v ufw &> /dev/null; then
    ufw allow $DjangoPort/tcp 2>/dev/null || true
    echo '>>> ufw: 端口 $DjangoPort 已开放'
fi

# 尝试用 firewalld
if command -v firewall-cmd &> /dev/null; then
    firewall-cmd --permanent --add-port=$DjangoPort/tcp 2>/dev/null || true
    firewall-cmd --reload 2>/dev/null || true
    echo '>>> firewalld: 端口 $DjangoPort 已开放'
fi

# 尝试用 iptables
if command -v iptables &> /dev/null; then
    iptables -I INPUT -p tcp --dport $DjangoPort -j ACCEPT 2>/dev/null || true
    echo '>>> iptables: 端口 $DjangoPort 已开放'
fi

echo ''
echo '========================================'
echo '  部署成功！'
echo '  访问地址: http://${ServerIP}:${DjangoPort}'
echo '========================================'
"@

if ($HasSshpass) {
    $env:SSHPASS = $PlainPassword
    $FirewallScript | & sshpass -e ssh $SSHOptions -p $ServerPort "${ServerUser}@${ServerIP}" "bash -s"
} else {
    $FirewallScript | ssh -o StrictHostKeyChecking=no -o UserKnownHostsFile=NUL -p $ServerPort "${ServerUser}@${ServerIP}" "bash -s"
}

# ========== 清理 ==========
Remove-Item $TempDir -Recurse -Force -ErrorAction SilentlyContinue
Remove-Item $ZipFile -Force -ErrorAction SilentlyContinue

# ========== 完成 ==========
Write-Host ""
Write-Host "========================================" -ForegroundColor Green
Write-Host "  部署完成！" -ForegroundColor Green
Write-Host "  访问地址: http://${ServerIP}:${DjangoPort}" -ForegroundColor Green
Write-Host "========================================" -ForegroundColor Green
Write-Host ""
Write-Host "管理命令：" -ForegroundColor Cyan
Write-Host "  查看状态: ssh ${ServerUser}@${ServerIP} 'systemctl status vocabmaster'"
Write-Host "  查看日志: ssh ${ServerUser}@${ServerIP} 'journalctl -u vocabmaster -f'"
Write-Host "  重启服务: ssh ${ServerUser}@${ServerIP} 'systemctl restart vocabmaster'"
Write-Host "  停止服务: ssh ${ServerUser}@${ServerIP} 'systemctl stop vocabmaster'"
Write-Host ""
