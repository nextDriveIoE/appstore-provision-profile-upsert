#!/usr/bin/env python3
"""
本地測試腳本
使用 .env 檔案載入環境變數來模擬 GitHub Action 執行環境
"""

import os
import sys
import tempfile
from pathlib import Path

def load_env_file(env_path: str = '.env'):
    """載入 .env 檔案中的環境變數"""
    env_file = Path(env_path)
    
    if not env_file.exists():
        print(f"❌ 找不到 {env_path} 檔案")
        print(f"請複製 .env.example 為 .env 並填入正確的參數值")
        print(f"\n  cp .env.example .env")
        print(f"  # 然後編輯 .env 檔案填入正確的值\n")
        sys.exit(1)
    
    print(f"📄 載入環境變數從: {env_path}")
    
    with open(env_file, 'r', encoding='utf-8') as f:
        for line_num, line in enumerate(f, 1):
            line = line.strip()
            
            # 跳過空行和註解
            if not line or line.startswith('#'):
                continue
            
            # 解析 KEY=VALUE 格式
            if '=' in line:
                key, value = line.split('=', 1)
                key = key.strip()
                value = value.strip()
                
                # 移除引號（如果有的話）
                if value.startswith('"') and value.endswith('"'):
                    value = value[1:-1]
                elif value.startswith("'") and value.endswith("'"):
                    value = value[1:-1]
                
                # 設置環境變數
                os.environ[key] = value
                
                # 只顯示部分敏感資訊
                if 'KEY' in key or 'SECRET' in key or 'BASE64' in key:
                    display_value = value[:10] + '...' if len(value) > 10 else '***'
                else:
                    display_value = value
                
                print(f"  ✓ {key} = {display_value}")
            else:
                print(f"  ⚠️  第 {line_num} 行格式錯誤: {line}")
    
    print()

def setup_github_output():
    """設置 GITHUB_OUTPUT 環境變數（如果未設置）"""
    if not os.environ.get('GITHUB_OUTPUT'):
        # 建立臨時檔案來模擬 GitHub Action 的輸出
        temp_output = tempfile.NamedTemporaryFile(mode='w', delete=False, suffix='_github_output.txt')
        output_path = temp_output.name
        temp_output.close()
        
        os.environ['GITHUB_OUTPUT'] = output_path
        print(f"📝 建立 GitHub Output 模擬檔案: {output_path}")
        print()
        return output_path
    return os.environ['GITHUB_OUTPUT']

def display_github_output(output_path: str):
    """顯示 GitHub Action 的輸出結果"""
    if os.path.exists(output_path):
        print("\n" + "="*60)
        print("📤 GitHub Action 輸出結果:")
        print("="*60)
        
        with open(output_path, 'r') as f:
            content = f.read().strip()
            if content:
                for line in content.split('\n'):
                    if '=' in line:
                        key, value = line.split('=', 1)
                        print(f"  {key} = {value}")
            else:
                print("  (無輸出)")
        
        print("="*60)
        
        # 清理臨時檔案
        try:
            os.unlink(output_path)
        except:
            pass

def main():
    """主函數"""
    print("\n" + "="*60)
    print("🚀 本地測試模式 - App Store Provision Profile Upsert")
    print("="*60 + "\n")
    
    # 載入 .env 檔案
    env_file = sys.argv[1] if len(sys.argv) > 1 else '.env'
    load_env_file(env_file)
    
    # 設置 GitHub Output
    output_path = setup_github_output()
    
    # 驗證必要參數
    required_params = [
        'PROFILE_NAME',
        'CERT_TYPE',
        'ISSUER_ID',
        'KEY_ID',
        'PRIVATE_KEY_BASE64',
        'BUNDLE_ID',
        'PROFILE_TYPE'
    ]
    
    missing_params = [param for param in required_params if not os.environ.get(param)]
    
    if missing_params:
        print(f"❌ 缺少必要參數: {', '.join(missing_params)}")
        print(f"\n請在 {env_file} 檔案中設置這些參數\n")
        sys.exit(1)
    
    print("✅ 所有必要參數已設置")
    print("\n" + "="*60)
    print("開始執行 main.py")
    print("="*60 + "\n")
    
    # 執行主程式
    try:
        # 將 src 目錄加入 Python 路徑
        src_dir = Path(__file__).parent / 'src'
        sys.path.insert(0, str(src_dir))
        
        # 導入並執行 main
        from main import main as run_main
        run_main()
        
        # 顯示輸出結果
        display_github_output(output_path)
        
    except Exception as e:
        print(f"\n❌ 執行失敗: {e}")
        import traceback
        traceback.print_exc()
        sys.exit(1)

if __name__ == '__main__':
    main()
