import Hero from './components/Hero';
import Features from './components/Features';
import Installation from './components/Installation';
import { Github, ArrowRight } from 'lucide-react';

function App() {
  return (
    <div className="min-h-screen">
      <Hero />
      <Features />
      <Installation />

      {/* CTA Section */}
      <section className="cta-gradient py-20">
        <div className="container text-center">
          <h2 className="text-3xl sm:text-4xl font-extrabold text-white mb-6">
            开始使用 Flask-Mdict
          </h2>
          <p className="text-blue-100 text-lg mb-10 max-w-xl mx-auto">
            现在就部署你的个人词典服务器，享受随时随地查词的便利。
          </p>
          <div className="flex flex-col sm:flex-row items-center justify-center gap-4">
            <a
              href="https://github.com/nxxxsooo/docker-flask-mdict"
              target="_blank"
              rel="noopener noreferrer"
              className="inline-flex items-center gap-2 px-8 py-4 bg-white text-blue-600 font-semibold rounded-full hover:bg-blue-50 transition-all shadow-lg"
            >
              <Github className="w-5 h-5" /> GitHub 仓库
            </a>
            <a
              href="#installation"
              className="inline-flex items-center gap-2 px-8 py-4 bg-white/10 text-white font-semibold rounded-full border border-white/30 hover:bg-white/20 transition-all"
            >
              查看文档 <ArrowRight className="w-5 h-5" />
            </a>
          </div>
        </div>
      </section>

      {/* Footer */}
      <footer className="py-10 bg-slate-900 text-center">
        <p className="text-slate-400 text-sm">
          © {new Date().getFullYear()} Docker Flask Mdict · 基于 MIT 协议开源
        </p>
      </footer>
    </div>
  );
}

export default App;
