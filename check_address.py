print('开始检查地址...')
address = '0xa54aa5C9BD63f83d275E41c981f24EACFe1A5BEE'
print('检查地址:', address)

addresses = set()
try:
    print('开始加载地址库...')
    with open('D:\\addresses_0 - 副本.txt', 'r', encoding='utf-8', errors='ignore') as f:
        line_count = 0
        for line in f:
            line_count += 1
            addr = line.strip()
            if addr:
                addresses.add(addr.lower())
            # 每1000行输出一次进度
            if line_count % 1000 == 0:
                print(f'已处理 {line_count} 行')
    print('地址库加载完成，共', len(addresses), '个地址')
    print('地址是否在库中:', address.lower() in addresses)
except Exception as e:
    print('错误:', str(e))
    import traceback
    traceback.print_exc()