import { motion } from 'framer-motion';
import { ArrowRight, Github } from 'lucide-react';

const Hero = () => {
    return (
        <section className="relative min-h-screen flex items-center overflow-hidden bg-gradient-to-br from-blue-50 via-white to-purple-50 py-20 px-4 sm:px-6 lg:px-8">
            {/* Background decorative elements */}
            <div className="absolute top-0 right-0 w-[600px] h-[600px] bg-blue-100/50 rounded-full blur-3xl -translate-y-1/2 translate-x-1/3" />
            <div className="absolute bottom-0 left-0 w-[400px] h-[400px] bg-purple-100/50 rounded-full blur-3xl translate-y-1/2 -translate-x-1/3" />

            <div className="container relative z-10">
                <div className="grid lg:grid-cols-2 gap-16 items-center">
                    {/* Left: Text content */}
                    <motion.div
                        initial={{ opacity: 0, x: -30 }}
                        animate={{ opacity: 1, x: 0 }}
                        transition={{ duration: 0.8 }}
                        className="text-center lg:text-left"
                    >
                        <span className="inline-block px-4 py-2 mb-6 text-sm font-semibold rounded-full bg-blue-100 text-blue-600">
                            🚀 开源免费 · 多平台支持
                        </span>

                        <h1 className="text-4xl sm:text-5xl lg:text-6xl font-extrabold leading-tight mb-6 text-slate-900">
                            现代化
                            <br />
                            <span className="gradient-text">词典查询平台</span>
                        </h1>

                        <p className="text-lg sm:text-xl text-slate-600 mb-10 leading-relaxed max-w-xl mx-auto lg:mx-0">
                            基于 Flask-Mdict 的 Docker 化部署方案。支持 LZO 压缩、多架构镜像、
                            反向代理，让你轻松搭建个人词典服务器。
                        </p>

                        <div className="flex flex-col sm:flex-row items-center justify-center lg:justify-start gap-4">
                            <a href="#installation" className="btn-primary">
                                立即开始 <ArrowRight className="w-5 h-5" />
                            </a>
                            <a
                                href="https://github.com/nxxxsooo/docker-flask-mdict"
                                target="_blank"
                                rel="noopener noreferrer"
                                className="btn-secondary"
                            >
                                <Github className="w-5 h-5" /> 查看源码
                            </a>
                        </div>
                    </motion.div>

                    {/* Right: Product mockup */}
                    <motion.div
                        initial={{ opacity: 0, x: 30 }}
                        animate={{ opacity: 1, x: 0 }}
                        transition={{ duration: 0.8, delay: 0.2 }}
                        className="relative hidden lg:block"
                    >
                        <div className="relative">
                            {/* Browser mockup */}
                            <div className="bg-white rounded-2xl shadow-2xl border border-slate-200 overflow-hidden">
                                {/* Browser bar */}
                                <div className="bg-slate-100 px-4 py-3 flex items-center gap-2 border-b border-slate-200">
                                    <div className="flex gap-1.5">
                                        <div className="w-3 h-3 rounded-full bg-red-400" />
                                        <div className="w-3 h-3 rounded-full bg-yellow-400" />
                                        <div className="w-3 h-3 rounded-full bg-green-400" />
                                    </div>
                                    <div className="flex-1 mx-4">
                                        <div className="bg-white rounded-md px-3 py-1.5 text-sm text-slate-500 border border-slate-200">
                                            localhost:5248
                                        </div>
                                    </div>
                                </div>
                                {/* Content area */}
                                <div className="p-6 bg-gradient-to-br from-slate-50 to-white min-h-[300px]">
                                    <div className="space-y-4">
                                        <div className="flex items-center gap-3">
                                            <div className="w-10 h-10 rounded-lg bg-blue-500 flex items-center justify-center text-white font-bold">M</div>
                                            <div className="font-semibold text-slate-800">Flask-Mdict</div>
                                        </div>
                                        <div className="bg-white rounded-lg p-4 border border-slate-100 shadow-sm">
                                            <div className="text-sm text-slate-500 mb-2">搜索词典</div>
                                            <div className="h-8 bg-slate-100 rounded-md" />
                                        </div>
                                        <div className="grid grid-cols-2 gap-3">
                                            <div className="bg-blue-50 rounded-lg p-3 text-center">
                                                <div className="text-2xl font-bold text-blue-600">10+</div>
                                                <div className="text-xs text-slate-500">词典数量</div>
                                            </div>
                                            <div className="bg-purple-50 rounded-lg p-3 text-center">
                                                <div className="text-2xl font-bold text-purple-600">100K+</div>
                                                <div className="text-xs text-slate-500">词条总数</div>
                                            </div>
                                        </div>
                                    </div>
                                </div>
                            </div>

                            {/* Floating cards */}
                            <motion.div
                                initial={{ opacity: 0, y: 20 }}
                                animate={{ opacity: 1, y: 0 }}
                                transition={{ delay: 0.6 }}
                                className="absolute -left-8 top-1/2 bg-white rounded-xl shadow-lg p-4 border border-slate-100"
                            >
                                <div className="flex items-center gap-3">
                                    <div className="w-10 h-10 rounded-full bg-green-100 flex items-center justify-center">
                                        <span className="text-green-600">✓</span>
                                    </div>
                                    <div>
                                        <div className="text-sm font-medium text-slate-800">LZO 支持</div>
                                        <div className="text-xs text-slate-500">兼容更多词典</div>
                                    </div>
                                </div>
                            </motion.div>
                        </div>
                    </motion.div>
                </div>
            </div>
        </section>
    );
};

export default Hero;
