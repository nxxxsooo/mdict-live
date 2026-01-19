import { motion } from 'framer-motion';
import { Archive, Globe, Layers, Database, Monitor, Shield } from 'lucide-react';

const features = [
    {
        icon: Archive,
        iconClass: 'icon-blue',
        title: "原生 LZO 支持",
        description: '内置 LZO 压缩解码，告别"未知压缩格式"错误，完美兼容老旧及中文词典。'
    },
    {
        icon: Globe,
        iconClass: 'icon-purple',
        title: "反向代理就绪",
        description: "集成 ProxyFix 中间件，正确处理 X-Forwarded 头，HTTPS 部署无压力。"
    },
    {
        icon: Layers,
        iconClass: 'icon-cyan',
        title: "多架构镜像",
        description: "同时支持 AMD64 服务器和 ARM64 树莓派，一套配置通吃全平台。"
    },
    {
        icon: Database,
        iconClass: 'icon-green',
        title: "数据持久化",
        description: "词典库与配置文件独立挂载，容器更新重启数据不丢失。"
    },
    {
        icon: Monitor,
        iconClass: 'icon-orange',
        title: "Web 界面",
        description: "浏览器直接访问，无需安装客户端，随时随地查词。"
    },
    {
        icon: Shield,
        iconClass: 'icon-pink',
        title: "安全精简",
        description: "默认绑定 0.0.0.0，精简镜像体积，移除冗余插件。"
    }
];

const FeatureCard = ({ feature, index }) => {
    return (
        <motion.div
            initial={{ opacity: 0, y: 30 }}
            whileInView={{ opacity: 1, y: 0 }}
            viewport={{ once: true, margin: "-50px" }}
            transition={{ duration: 0.5, delay: index * 0.1 }}
            className="feature-card"
        >
            <div className={`icon-wrapper ${feature.iconClass}`}>
                <feature.icon className="w-6 h-6" />
            </div>
            <h3 className="text-xl font-bold mb-3 text-slate-800">{feature.title}</h3>
            <p className="text-slate-600 leading-relaxed">
                {feature.description}
            </p>
        </motion.div>
    );
};

const Features = () => {
    return (
        <section className="section-padding bg-slate-50/50">
            <div className="container">
                <motion.div
                    initial={{ opacity: 0, y: 20 }}
                    whileInView={{ opacity: 1, y: 0 }}
                    viewport={{ once: true }}
                    className="text-center mb-16"
                >
                    <span className="inline-block px-4 py-2 mb-4 text-sm font-semibold rounded-full bg-purple-100 text-purple-600">
                        核心特性
                    </span>
                    <h2 className="text-3xl sm:text-4xl lg:text-5xl font-extrabold mb-6 text-slate-900">
                        为 <span className="gradient-text">效率而生</span>
                    </h2>
                    <p className="text-lg text-slate-600 max-w-2xl mx-auto">
                        精心打造的现代化词典服务器，满足你对性能与稳定性的全部期待。
                    </p>
                </motion.div>

                <div className="grid grid-cols-1 md:grid-cols-2 lg:grid-cols-3 gap-5 md:gap-6 lg:gap-8">
                    {features.map((feature, index) => (
                        <FeatureCard key={index} feature={feature} index={index} />
                    ))}
                </div>
            </div>
        </section>
    );
};

export default Features;
