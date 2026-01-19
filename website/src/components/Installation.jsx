import { useState } from 'react';
import { motion } from 'framer-motion';
import { Terminal, Copy, Check, ArrowRight } from 'lucide-react';

const CodeBlock = ({ title, code }) => {
    const [copied, setCopied] = useState(false);

    const handleCopy = () => {
        navigator.clipboard.writeText(code);
        setCopied(true);
        setTimeout(() => setCopied(false), 2000);
    };

    return (
        <div className="mb-6">
            <div className="flex items-center gap-2 mb-3 text-slate-700 font-medium">
                <Terminal className="w-4 h-4 text-blue-500" />
                {title}
            </div>
            <div className="relative group">
                <pre className="bg-slate-900 text-slate-300 rounded-xl p-5 overflow-x-auto text-sm font-mono leading-relaxed">
                    <code>{code}</code>
                </pre>
                <button
                    onClick={handleCopy}
                    className="absolute top-3 right-3 p-2.5 bg-slate-800 hover:bg-slate-700 rounded-lg text-slate-400 hover:text-white transition-all opacity-0 group-hover:opacity-100"
                    title="复制代码"
                >
                    {copied ? <Check className="w-4 h-4 text-green-400" /> : <Copy className="w-4 h-4" />}
                </button>
            </div>
        </div>
    );
};

const Installation = () => {
    const dockerRun = `docker run -d \\
  --name flask-mdict \\
  -p 5248:5248 \\
  -v $(pwd)/library:/app/content \\
  tardivo/flask-mdict:latest`;

    const dockerCompose = `version: '3.8'
services:
  flask-mdict:
    image: tardivo/flask-mdict:latest
    ports:
      - "5248:5248"
    volumes:
      - ./library:/app/content
      - ./config:/config
    restart: always`;

    return (
        <section id="installation" className="section-padding">
            <div className="container">
                <div className="max-w-4xl mx-auto">
                    <motion.div
                        initial={{ opacity: 0, y: 20 }}
                        whileInView={{ opacity: 1, y: 0 }}
                        viewport={{ once: true }}
                        className="text-center mb-12"
                    >
                        <span className="inline-block px-4 py-2 mb-4 text-sm font-semibold rounded-full bg-cyan-100 text-cyan-600">
                            快速部署
                        </span>
                        <h2 className="text-3xl sm:text-4xl lg:text-5xl font-extrabold mb-6 text-slate-900">
                            三步启动
                        </h2>
                        <p className="text-lg text-slate-600">
                            只需 Docker，几分钟即可拥有你的专属词典服务器。
                        </p>
                    </motion.div>

                    <motion.div
                        initial={{ opacity: 0, y: 30 }}
                        whileInView={{ opacity: 1, y: 0 }}
                        viewport={{ once: true }}
                        className="bg-white rounded-2xl shadow-xl border border-slate-100 p-8 sm:p-10"
                    >
                        <CodeBlock title="Docker CLI" code={dockerRun} />
                        <CodeBlock title="Docker Compose" code={dockerCompose} />

                        <div className="mt-8 p-5 bg-blue-50 border border-blue-100 rounded-xl">
                            <p className="text-blue-800 text-sm">
                                <strong className="font-semibold">💡 提示：</strong>
                                请先创建 <code className="bg-blue-100 px-1.5 py-0.5 rounded text-blue-700">library</code> 文件夹并放入你的 .mdx/.mdd 词典文件。
                            </p>
                        </div>
                    </motion.div>
                </div>
            </div>
        </section>
    );
};

export default Installation;
