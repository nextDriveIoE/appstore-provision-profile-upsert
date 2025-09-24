.PHONY: help install test local-test clean lint format check

# 默認目標
help:
	@echo "App Store Provision Profile Upsert Action"
	@echo "========================================="
	@echo ""
	@echo "可用命令："
	@echo "  install     - 安裝依賴套件"
	@echo "  test        - 執行本地測試"
	@echo "  lint        - 程式碼檢查"
	@echo "  format      - 程式碼格式化"
	@echo "  clean       - 清理暫存檔案"
	@echo "  check       - 檢查專案設定"

# 安裝依賴
install:
	@echo "📦 安裝 Python 依賴套件..."
	pip install -r requirements.txt
	pip install flake8 black pylint

# 本地測試
test: local-test

local-test:
	@echo "🧪 執行本地測試..."
	@echo "注意：請先設置正確的 API 金鑰環境變數"
	python test_local.py

# 程式碼檢查
lint:
	@echo "🔍 執行程式碼檢查..."
	flake8 src/ --max-line-length=100 --ignore=E203,W503
	pylint src/ --disable=C0111,C0103

# 程式碼格式化
format:
	@echo "✨ 格式化程式碼..."
	black src/ --line-length=100
	black test_local.py --line-length=100

# 清理暫存檔案
clean:
	@echo "🧹 清理暫存檔案..."
	find . -type f -name "*.pyc" -delete
	find . -type d -name "__pycache__" -exec rm -rf {} +
	find . -type f -name "*.tmp" -delete
	find . -type f -name "*.log" -delete
	rm -f /tmp/github_output.txt

# 檢查專案設定
check:
	@echo "🔧 檢查專案設定..."
	@echo "Python 版本:"
	python --version
	@echo ""
	@echo "已安裝套件:"
	pip list | grep -E "(applaud|cryptography)"
	@echo ""
	@echo "檔案結構："
	tree . -I '__pycache__|*.pyc|.git' || find . -type f -name "*.py" -o -name "*.yml" -o -name "*.md" | head -20

# 準備發布
prepare-release:
	@echo "🚀 準備發布..."
	$(MAKE) clean
	$(MAKE) format
	$(MAKE) lint
	@echo "✅ 準備完成，可以提交到 Git"

# 快速設置（首次使用）
setup:
	@echo "🏁 首次設置..."
	$(MAKE) install
	@echo ""
	@echo "📝 下一步："
	@echo "1. 設置環境變數（API 金鑰）："
	@echo "   export ISSUER_ID='your-issuer-id'"
	@echo "   export KEY_ID='your-key-id'"
	@echo "   export PRIVATE_KEY_BASE64='your-base64-private-key'"
	@echo ""
	@echo "2. 執行測試："
	@echo "   make test"
	@echo ""
	@echo "3. 在 GitHub Repository 中設置 Secrets"
