import tkinter as tk
from tkinter import filedialog, messagebox, scrolledtext
import os
import threading
import time
from eth_account import Account
from mnemonic import Mnemonic
import json
import psutil
import mmap

# 启用HD钱包功能
Account.enable_unaudited_hdwallet_features()

class EVMAddressScanner:
    def __init__(self, root):
        self.root = root
        self.root.title("EVM地址扫描器")
        self.root.geometry("600x400")
        self.root.resizable(False, False)
        
        # 状态变量
        self.is_running = False
        self.is_paused = False
        self.address_db = set()
        self.results = []
        self.threads = []
        self.num_threads = 8  # 16线程的50%左右
        
        # 地址保存相关变量
        self.generated_addresses_count = 0
        self.current_file_index = 0
        self.addresses_per_file = 1000000
        self.addresses_dir = "generated_addresses"
        self.mnemonics_dir = "generated_mnemonics"
        self.index_dir = "address_indexes"
        
        # 助记词去重相关变量
        self.mnemonic_set = set()
        self.mnemonics_file = "mnemonics_set.json"
        self.mnemonic_lock = threading.Lock()  # 线程安全锁
        
        # 内存限制（16GB）
        self.max_memory_usage = 16 * 1024 * 1024 * 1024  # 16GB
        
        # 索引相关变量
        self.address_index = {}
        self.index_lock = threading.Lock()
        
        # 创建保存目录
        if not os.path.exists(self.addresses_dir):
            os.makedirs(self.addresses_dir)
        if not os.path.exists(self.mnemonics_dir):
            os.makedirs(self.mnemonics_dir)
        if not os.path.exists(self.index_dir):
            os.makedirs(self.index_dir)
        
        # 创建UI组件
        self.create_widgets()
        
        # 加载已生成的助记词和索引
        self.load_mnemonics()
        self.load_index()
    
    def create_widgets(self):
        # 主框架
        main_frame = tk.Frame(self.root, padx=20, pady=20)
        main_frame.pack(fill=tk.BOTH, expand=True)
        
        # 按钮框架
        button_frame = tk.Frame(main_frame)
        button_frame.pack(fill=tk.X, pady=10)
        
        # 导入数据库按钮
        self.import_btn = tk.Button(button_frame, text="导入数据库", command=self.import_database, width=15)
        self.import_btn.pack(side=tk.LEFT, padx=5)
        
        # 开始按钮
        self.start_btn = tk.Button(button_frame, text="开始", command=self.start_scanning, width=15, state=tk.DISABLED)
        self.start_btn.pack(side=tk.LEFT, padx=5)
        
        # 暂停按钮
        self.pause_btn = tk.Button(button_frame, text="暂停", command=self.pause_scanning, width=15, state=tk.DISABLED)
        self.pause_btn.pack(side=tk.LEFT, padx=5)
        
        # 停止按钮
        self.stop_btn = tk.Button(button_frame, text="停止", command=self.stop_scanning, width=15, state=tk.DISABLED)
        self.stop_btn.pack(side=tk.LEFT, padx=5)
        
        # 查看结果按钮
        self.view_btn = tk.Button(button_frame, text="查看结果", command=self.view_results, width=15, state=tk.DISABLED)
        self.view_btn.pack(side=tk.LEFT, padx=5)
        
        # 合并和清理按钮
        self.merge_btn = tk.Button(button_frame, text="合并和清理", command=self.merge_and_clean, width=15)
        self.merge_btn.pack(side=tk.LEFT, padx=5)
        
        # 状态标签
        self.status_var = tk.StringVar()
        self.status_var.set("就绪")
        self.status_label = tk.Label(main_frame, textvariable=self.status_var, font=("Arial", 12))
        self.status_label.pack(pady=10)
        
        # 信息文本框
        self.info_text = scrolledtext.ScrolledText(main_frame, height=10, wrap=tk.WORD)
        self.info_text.pack(fill=tk.BOTH, expand=True, pady=10)
        self.info_text.config(state=tk.DISABLED)
    
    def log(self, message):
        """记录日志信息"""
        self.info_text.config(state=tk.NORMAL)
        self.info_text.insert(tk.END, f"{time.strftime('%Y-%m-%d %H:%M:%S')} - {message}\n")
        self.info_text.see(tk.END)
        self.info_text.config(state=tk.DISABLED)
    
    def import_database(self):
        """导入地址数据库"""
        file_paths = filedialog.askopenfilenames(
            title="选择地址数据库文件",
            filetypes=[("文本文件", "*.txt *.csv"), ("CSV文件", "*.csv"), ("所有文件", "*.*")]
        )
        
        if not file_paths:
            return
        
        try:
            self.status_var.set("正在导入数据库...")
            self.log(f"开始导入数据库，共 {len(file_paths)} 个文件")
            
            # 清空现有数据库
            self.address_db.clear()
            total_line_count = 0
            
            # 读取每个文件并添加到集合中
            for file_path in file_paths:
                self.log(f"导入文件: {file_path}")
                line_count = 0
                
                # 使用内存映射文件处理大文件
                with open(file_path, 'r+b') as f:
                    # 创建内存映射
                    mm = mmap.mmap(f.fileno(), 0)
                    try:
                        # 逐行读取
                        line = mm.readline()
                        while line:
                            address = line.decode('utf-8', errors='ignore').strip()
                            if address:
                                self.address_db.add(address)
                                line_count += 1
                                total_line_count += 1
                            
                            # 每100万行更新一次状态
                            if line_count % 1000000 == 0:
                                self.log(f"已导入 {line_count} 个地址 (当前文件)")
                            
                            line = mm.readline()
                    finally:
                        mm.close()
                
                self.log(f"文件导入完成，当前文件导入 {line_count} 个地址")
            
            self.log(f"数据库导入完成，共 {len(self.address_db)} 个地址")
            self.status_var.set(f"就绪 - 已导入 {len(self.address_db)} 个地址")
            
            # 启用开始按钮
            self.start_btn.config(state=tk.NORMAL)
        except Exception as e:
            messagebox.showerror("错误", f"导入数据库时出错: {str(e)}")
            self.status_var.set("就绪")
    
    def start_scanning(self):
        """开始扫描"""
        if not self.address_db:
            messagebox.showwarning("警告", "请先导入地址数据库")
            return
        
        self.is_running = True
        self.is_paused = False
        
        # 更新按钮状态
        self.start_btn.config(state=tk.DISABLED)
        self.pause_btn.config(state=tk.NORMAL)
        self.stop_btn.config(state=tk.NORMAL)
        self.import_btn.config(state=tk.DISABLED)
        
        self.status_var.set("扫描中...")
        self.log(f"开始扫描EVM地址，使用 {self.num_threads} 个线程")
        
        # 启动多个扫描线程
        self.threads = []
        for i in range(self.num_threads):
            thread = threading.Thread(target=self.scan_addresses, args=(i,))
            thread.daemon = True
            thread.start()
            self.threads.append(thread)
    
    def pause_scanning(self):
        """暂停扫描"""
        self.is_paused = not self.is_paused
        if self.is_paused:
            self.status_var.set("已暂停")
            self.pause_btn.config(text="继续")
            self.log("扫描已暂停")
        else:
            self.status_var.set("扫描中...")
            self.pause_btn.config(text="暂停")
            self.log("扫描继续")
    
    def stop_scanning(self):
        """停止扫描"""
        self.is_running = False
        
        # 等待所有线程结束
        for thread in self.threads:
            thread.join(timeout=2)
        
        # 更新按钮状态
        self.start_btn.config(state=tk.NORMAL)
        self.pause_btn.config(state=tk.DISABLED)
        self.stop_btn.config(state=tk.DISABLED)
        self.import_btn.config(state=tk.NORMAL)
        
        if self.results:
            self.view_btn.config(state=tk.NORMAL)
        
        # 保存助记词集合和索引
        self.save_mnemonics()
        self.save_index()
        
        self.status_var.set("已停止")
        self.log("扫描已停止")
    
    def scan_addresses(self, thread_id):
        """扫描EVM地址"""
        generated_count = 0
        start_time = time.time()
        last_status_update = time.time()
        batch_size = 5000  # 批量处理大小
        
        # 预创建Mnemonic实例
        mnemo = Mnemonic("english")
        
        # 批量保存地址的缓冲区
        address_buffer = []
        
        while self.is_running:
            # 检查是否暂停
            while self.is_paused and self.is_running:
                time.sleep(0.1)
            
            if not self.is_running:
                break
            
            # 检查内存使用情况
            process = psutil.Process()
            memory_info = process.memory_info()
            if memory_info.rss > self.max_memory_usage:
                self.log(f"线程 {thread_id}: 内存使用超过限制，暂停运行")
                time.sleep(1)
                continue
            
            # 批量生成地址
            for _ in range(batch_size):
                if not self.is_running:
                    break
                
                # 生成不重复的助记词（线程安全）
                while True:
                    # 使用128位强度生成12个单词的助记词
                    temp_mnemonic = mnemo.generate(strength=128)
                    # 验证助记词是否为12个单词
                    words = temp_mnemonic.split()
                    if len(words) != 12:
                        continue
                    with self.mnemonic_lock:
                        if temp_mnemonic not in self.mnemonic_set:
                            mnemonic_phrase = temp_mnemonic
                            self.mnemonic_set.add(mnemonic_phrase)
                            break
                
                # 使用助记词创建账户
                account = Account.from_mnemonic(mnemonic_phrase)
                address = account.address
                
                generated_count += 1
                with self.mnemonic_lock:
                    self.generated_addresses_count += 1
                
                # 添加到地址缓冲区（同时保存地址和助记词）
                address_buffer.append((address, mnemonic_phrase))
                
                # 检查地址是否在数据库中
                if address in self.address_db:
                    # 记录匹配结果
                    result = {
                        "address": address,
                        "mnemonic": mnemonic_phrase,
                        "timestamp": time.strftime("%Y-%m-%d %H:%M:%S")
                    }
                    with self.mnemonic_lock:
                        self.results.append(result)
                    
                    # 保存到文件
                    self.save_result(result)
                    
                    self.log(f"找到匹配地址: {address}")
            
            # 批量保存地址和助记词
            for addr, mnemonic in address_buffer:
                self.save_generated_address(addr)
                self.save_generated_mnemonic(mnemonic)
            address_buffer.clear()
            
            # 每1000个助记词保存一次
            with self.mnemonic_lock:
                if len(self.mnemonic_set) % 1000 == 0:
                    self.save_mnemonics()
            
            # 每一分钟更新一次状态
            current_time = time.time()
            if current_time - last_status_update >= 60:
                # 检查内存使用情况
                memory = psutil.virtual_memory()
                memory_usage = memory.percent
                
                # 记录内存使用情况
                if memory_usage > 80:
                    self.log(f"警告: 内存使用过高 - {memory_usage:.2f}%")
                
                elapsed = time.time() - start_time
                speed = generated_count / elapsed
                with self.mnemonic_lock:
                    total_count = self.generated_addresses_count
                self.status_var.set(f"扫描中 - 已生成 {total_count} 个地址 ({speed:.2f} 地址/秒) - 内存: {memory_usage:.2f}%")
                last_status_update = current_time
    
    def save_result(self, result):
        """保存匹配结果到文件"""
        with open("results.txt", "a", encoding="utf-8") as f:
            f.write(f"地址: {result['address']}\n")
            f.write(f"助记词: {result['mnemonic']}\n")
            f.write(f"时间: {result['timestamp']}\n")
            f.write("-" * 80 + "\n")
    
    def save_generated_address(self, address):
        """保存生成的地址到文件，每个文件最多100万行"""
        # 计算当前文件索引
        file_index = self.generated_addresses_count // self.addresses_per_file
        
        # 如果文件索引变化，更新当前文件索引
        if file_index != self.current_file_index:
            self.current_file_index = file_index
            
        # 生成文件名
        file_name = f"{self.addresses_dir}/addresses_{self.current_file_index}.csv"
        
        # 计算行号
        line_number = self.generated_addresses_count % self.addresses_per_file + 1
        
        # 写入地址
        with open(file_name, "a", encoding="utf-8") as f:
            f.write(address + "\n")
        
        # 添加到索引
        self.add_to_index(address, file_index, line_number)
    
    def save_generated_mnemonic(self, mnemonic):
        """保存生成的助记词到文件，每个文件最多100万行"""
        # 计算当前文件索引
        file_index = self.generated_addresses_count // self.addresses_per_file
        
        # 生成文件名
        file_name = f"{self.mnemonics_dir}/mnemonics_{file_index}.csv"
        
        # 写入助记词
        with open(file_name, "a", encoding="utf-8") as f:
            f.write(mnemonic + "\n")
    
    def load_mnemonics(self):
        """加载已生成的助记词集合"""
        try:
            if os.path.exists(self.mnemonics_file):
                with open(self.mnemonics_file, "r", encoding="utf-8") as f:
                    data = json.load(f)
                    self.mnemonic_set = set(data)
                self.log(f"已加载 {len(self.mnemonic_set)} 个助记词")
        except Exception as e:
            self.log(f"加载助记词失败: {str(e)}")
    
    def save_mnemonics(self):
        """保存助记词集合到文件"""
        try:
            with open(self.mnemonics_file, "w", encoding="utf-8") as f:
                json.dump(list(self.mnemonic_set), f)
        except Exception as e:
            self.log(f"保存助记词失败: {str(e)}")
    
    def add_to_index(self, address, file_index, line_number):
        """添加地址到索引"""
        with self.index_lock:
            self.address_index[address] = {
                "file_index": file_index,
                "line_number": line_number
            }
    
    def save_index(self):
        """保存索引到文件"""
        try:
            index_file = f"{self.index_dir}/address_index.json"
            with open(index_file, "w", encoding="utf-8") as f:
                json.dump(self.address_index, f)
        except Exception as e:
            self.log(f"保存索引失败: {str(e)}")
    
    def load_index(self):
        """加载索引从文件"""
        try:
            index_file = f"{self.index_dir}/address_index.json"
            if os.path.exists(index_file):
                with open(index_file, "r", encoding="utf-8") as f:
                    self.address_index = json.load(f)
                self.log(f"已加载 {len(self.address_index)} 个地址索引")
        except Exception as e:
            self.log(f"加载索引失败: {str(e)}")
    
    def merge_and_clean(self):
        """合并小文件并清理重复地址"""
        self.log("开始合并和清理文件...")
        
        try:
            # 合并地址文件
            self.merge_files(self.addresses_dir, "addresses_", ".csv")
            
            # 合并助记词文件
            self.merge_files(self.mnemonics_dir, "mnemonics_", ".csv")
            
            # 清理重复地址
            self.clean_duplicates()
            
            self.log("合并和清理完成")
        except Exception as e:
            self.log(f"合并和清理失败: {str(e)}")
    
    def merge_files(self, directory, prefix, extension):
        """合并目录中的文件"""
        files = []
        for filename in os.listdir(directory):
            if filename.startswith(prefix) and filename.endswith(extension):
                files.append(os.path.join(directory, filename))
        
        if len(files) <= 1:
            return
        
        # 按文件名排序
        files.sort()
        
        # 创建合并文件
        merged_file = os.path.join(directory, f"{prefix}merged{extension}")
        
        # 合并文件内容
        with open(merged_file, "w", encoding="utf-8") as outfile:
            for file_path in files:
                with open(file_path, "r", encoding="utf-8") as infile:
                    outfile.write(infile.read())
        
        # 删除原文件
        for file_path in files:
            os.remove(file_path)
        
        # 重命名合并文件
        new_name = os.path.join(directory, f"{prefix}0{extension}")
        os.rename(merged_file, new_name)
        
        self.log(f"合并了 {len(files)} 个文件到 {new_name}")
    
    def clean_duplicates(self):
        """清理重复地址"""
        # 收集所有地址
        all_addresses = set()
        duplicate_count = 0
        
        # 读取所有地址文件
        for filename in os.listdir(self.addresses_dir):
            if filename.endswith(".csv"):
                file_path = os.path.join(self.addresses_dir, filename)
                with open(file_path, "r", encoding="utf-8") as f:
                    for line in f:
                        address = line.strip()
                        if address:
                            if address in all_addresses:
                                duplicate_count += 1
                            else:
                                all_addresses.add(address)
        
        if duplicate_count > 0:
            # 重写文件，只保留唯一地址
            file_path = os.path.join(self.addresses_dir, "addresses_0.csv")
            with open(file_path, "w", encoding="utf-8") as f:
                for address in all_addresses:
                    f.write(address + "\n")
            
            # 删除其他文件
            for filename in os.listdir(self.addresses_dir):
                if filename != "addresses_0.csv" and filename.endswith(".csv"):
                    os.remove(os.path.join(self.addresses_dir, filename))
            
            self.log(f"清理了 {duplicate_count} 个重复地址")
    
    def view_results(self):
        """查看匹配结果"""
        if not self.results:
            messagebox.showinfo("信息", "暂无匹配结果")
            return
        
        # 创建结果窗口
        result_window = tk.Toplevel(self.root)
        result_window.title("匹配结果")
        result_window.geometry("800x500")
        
        # 创建结果文本框
        result_text = scrolledtext.ScrolledText(result_window, wrap=tk.WORD)
        result_text.pack(fill=tk.BOTH, expand=True, padx=10, pady=10)
        
        # 显示结果
        for i, result in enumerate(self.results, 1):
            result_text.insert(tk.END, f"结果 {i}:\n")
            result_text.insert(tk.END, f"地址: {result['address']}\n")
            result_text.insert(tk.END, f"助记词: {result['mnemonic']}\n")
            result_text.insert(tk.END, f"时间: {result['timestamp']}\n")
            result_text.insert(tk.END, "-" * 80 + "\n")
        
        result_text.config(state=tk.DISABLED)

if __name__ == "__main__":
    root = tk.Tk()
    app = EVMAddressScanner(root)
    root.mainloop()
