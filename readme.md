#### 背景

迷你定向网页抓取器（百度的一个题）：

 

使用python做定向抓取比较简单。请使用python开发一个迷你定向抓取器`mini_spider.py`，实现对种子链接的抓取，并把URL长相符合特定pattern的网页保存到磁盘上。 程序运行:

`python mini_spider.py -c spider.conf `

 

配置文件spider.conf:

```
[spider] 

url_list_file: ./urls ; 种子文件路径 

output_directory: ./output ; 抓取结果存储目录

max_depth: 1 ; 最大抓取深度(种子为0级) 

crawl_interval: 1 ; 抓取间隔. 单位: 秒 

crawl_timeout: 1 ; 抓取超时. 单位: 秒 

target_url: .*.(htm|html)$ ; 需要存储的目标网页URL pattern(正则表达式) 

thread_count: 8 ; 抓取线程数 
```



种子文件每行一条链接，例如:

```
http://www.baidu.com 

http://www.sina.com.cn 
```



要求和注意事项:

- 需要支持命令行参数处理。具体包含: -h(帮助)、-v(版本)、-c(配置文件)

- 单个网页抓取或解析失败，不能导致整个程序退出。需要在日志中记录下错误原因并继续。

- 当程序完成所有抓取任务后，必须优雅退出。

- 从HTML提取链接时需要处理相对路径和绝对路径。

- 需要能够处理不同字符编码的网页(例如utf-8或gbk)。

- 网页存储时每个网页单独存为一个文件，以URL为文件名。注意对URL中的特殊字符，需要做转义。

- 要求支持多线程并行抓取。

- 代码严格遵守百度python编码规范

- 代码的可读性和可维护性好。注意模块、类、函数的设计和划分









#### 启动

`python3 mini_spider.py -c spider.conf`

#### 查看帮助
`python3 mini_spider.py -h`

#### 查看版本
`python3 mini_spider.py -v`