import React, { useState, useEffect, useRef } from 'react';

// --- 모의 데이터 (실제 환경에서는 수집된 jw_multilingual_data.json을 Fetch하여 사용) ---
const MOCK_DB = [
  {
    id: "osg_001",
    title: "우리 함께 있어요 (We Are There for Each Other)",
    cover_url: "https://placehold.co/600x600/1e293b/f8fafc?text=JW+Original+Song",
    audio_url: "https://www.soundhelix.com/examples/mp3/SoundHelix-Song-1.mp3", // 테스트용 오디오
    lyrics: {
      ko: [
        { start: 0, end: 5, text: "어떤 어려움을 겪더라도" },
        { start: 5, end: 12, text: "우리가 함께라면 이겨낼 수 있어요" },
        { start: 12, end: 20, text: "달콤한 한마디 우리의 말에는" },
        { start: 20, end: 30, text: "정말 큰 힘이 있어요 함께라면" }
      ],
      en: [
        { start: 0, end: 5, text: "No matter what trials come our way" },
        { start: 5, end: 12, text: "We'll stand together, come what may" },
        { start: 12, end: 20, text: "A gentle word can heal and bless" },
        { start: 20, end: 30, text: "Bringing true peace and happiness" }
      ],
      cn: [
        { start: 0, end: 5, text: "无论面对什么艰难险阻" },
        { start: 5, end: 12, text: "只要我们并肩就能战胜一切" },
        { start: 12, end: 20, text: "一句温言充满着力量" },
        { start: 20, end: 30, text: "带给我们无限的安慰" }
      ]
    }
  }
];

export default function App() {
  const [currentSongIndex, setCurrentSongIndex] = useState(0);
  const [isPlaying, setIsPlaying] = useState(false);
  const [currentTime, setCurrentTime] = useState(0);
  const [duration, setDuration] = useState(0);
  const [lang, setLang] = useState('ko'); // ko, en, cn
  const [autoSync, setAutoSync] = useState(true); // 외부 미디어 자동 연동 모드
  const [detectedTitle, setDetectedTitle] = useState("재생 중인 미디어 감지 대기 중...");

  const audioRef = useRef(null);
  const song = MOCK_DB[currentSongIndex];
  const activeLyrics = song.lyrics[lang] || [];

  useEffect(() => {
    const audio = audioRef.current;
    if (!audio) return;

    const handleTimeUpdate = () => setCurrentTime(audio.currentTime);
    const handleLoadedMetadata = () => setDuration(audio.duration);
    const handleEnded = () => handleNext();

    audio.addEventListener('timeupdate', handleTimeUpdate);
    audio.addEventListener('loadedmetadata', handleLoadedMetadata);
    audio.addEventListener('ended', handleEnded);

    return () => {
      audio.removeEventListener('timeupdate', handleTimeUpdate);
      audio.removeEventListener('loadedmetadata', handleLoadedMetadata);
      audio.removeEventListener('ended', handleEnded);
    };
  }, [currentSongIndex]);

  useEffect(() => {
    // 아이폰/사파리에서 현재 기기(Apple Music 등) 재생 정보를 연동하는 로직
    if ('mediaSession' in navigator) {
      navigator.mediaSession.setActionHandler('play', () => togglePlay());
      navigator.mediaSession.setActionHandler('pause', () => togglePlay());
      navigator.mediaSession.setActionHandler('nexttrack', () => handleNext());
      navigator.mediaSession.setActionHandler('previoustrack', () => handlePrev());

      // 주기적으로 MediaSession 상태를 체크하여 외부 앱(유튜브 뮤직 등) 제목 동기화 시도
      const interval = setInterval(() => {
        if (autoSync && navigator.mediaSession.metadata) {
          const title = navigator.mediaSession.metadata.title;
          if (title) {
            setDetectedTitle(title);
            // 만약 제목이 DB에 존재한다면 자동으로 해당 곡으로 스위치하는 로직 확장 가능
          }
        }
      }, 2000);
      return () => clearInterval(interval);
    }
  }, [autoSync]);

  const togglePlay = () => {
    const audio = audioRef.current;
    if (!audio) return;
    if (isPlaying) {
      audio.pause();
    } else {
      audio.play().catch(e => console.log("Playback error:", e));
    }
    setIsPlaying(!isPlaying);
  };

  const handleNext = () => {
    setCurrentSongIndex((prev) => (prev + 1) % MOCK_DB.length);
    setIsPlaying(false);
    setCurrentTime(0);
  };

  const handlePrev = () => {
    setCurrentSongIndex((prev) => (prev - 1 + MOCK_DB.length) % MOCK_DB.length);
    setIsPlaying(false);
    setCurrentTime(0);
  };

  // 현재 시간에 맞는 활성 가사 인덱스 찾기
  const activeIndex = activeLyrics.findIndex(
    (line, idx) => {
      const nextLine = activeLyrics[idx + 1];
      return currentTime >= line.start && (!nextLine || currentTime < nextLine.start);
    }
  );

  return (
    <div className="relative min-h-screen w-full bg-slate-950 text-slate-100 flex flex-col justify-between overflow-hidden font-sans select-none">
      {/* 백그라운드 앰비언트 블러 처리 (앨범 아트 기반) */}
      <div className="absolute inset-0 opacity-25 filter blur-3xl pointer-events-none scale-125 transform">
        <img src={song.cover_url} alt="background blur" className="w-full h-full object-cover" />
      </div>

      {/* 상단 헤더 & 외부 기기 싱크 모니터 */}
      <header className="relative z-10 p-4 flex items-center justify-between border-b border-slate-800/40 backdrop-blur-md">
        <div className="flex items-center space-x-2">
          <span className="inline-block w-2.5 h-2.5 rounded-full bg-emerald-500 animate-pulse"></span>
          <span className="text-xs text-slate-400 font-medium tracking-wide truncate max-w-[200px]">
            {autoSync ? `연동됨: ${detectedTitle}` : "수동 재생 모드"}
          </span>
        </div>
        
        {/* 언어 선택 탭 */}
        <div className="flex bg-slate-900/80 p-1 rounded-full border border-slate-800">
          {['ko', 'en', 'cn'].map((l) => (
            <button
              key={l}
              onClick={() => setLang(l)}
              className={`px-3 py-1 text-xs font-semibold rounded-full transition-all ${
                lang === l ? 'bg-slate-100 text-slate-950 shadow-sm' : 'text-slate-400 hover:text-slate-200'
              }`}
            >
              {l.toUpperCase()}
            </button>
          ))}
        </div>
      </header>

      {/* 중앙 가사 뷰어 영역 (유튜브 뮤직 스타일 시인성 극대화) */}
      <main className="relative z-10 flex-1 flex flex-col items-center justify-center px-6 py-8 overflow-y-auto max-w-xl mx-auto w-full no-scrollbar">
        {activeLyrics.length === 0 ? (
          <div className="text-slate-500 text-sm tracking-widest uppercase">자막 데이터가 없습니다</div>
        ) : (
          <div className="space-y-8 w-full text-center py-20">
            {activeLyrics.map((line, idx) => {
              const isActive = idx === activeIndex;
              const isPast = idx < activeIndex;
              return (
                <p
                  key={idx}
                  onClick={() => {
                    if (audioRef.current) audioRef.current.currentTime = line.start;
                  }}
                  className={`transition-all duration-300 cursor-pointer px-4 ${
                    isActive 
                      ? 'text-2xl md:text-3xl font-bold text-white scale-105 tracking-tight drop-shadow-md' 
                      : isPast 
                      ? 'text-lg md:text-xl font-medium text-slate-500 opacity-60 blur-[0.3px]' 
                      : 'text-lg md:text-xl font-medium text-slate-400 opacity-40 hover:opacity-75'
                  }`}
                >
                  {line.text}
                </p>
              );
            })}
          </div>
        )}
      </main>

      {/* 하단 컨트롤 패널 및 미니 썸네일 */}
      <footer className="relative z-10 p-6 bg-slate-900/60 backdrop-blur-xl border-t border-slate-800/50 flex flex-col space-y-4">
        {/* 곡 정보 및 미니 앨범 아트 */}
        <div className="flex items-center space-x-4">
          <img 
            src={song.cover_url} 
            alt="cover" 
            className="w-14 h-14 rounded-xl object-cover shadow-lg border border-slate-700/50 flex-shrink-0" 
          />
          <div className="flex-1 min-w-0">
            <h2 className="text-base font-bold text-slate-100 truncate tracking-tight">{song.title}</h2>
            <p className="text-xs text-slate-400 truncate mt-0.5">JW Original Songs & Hymns</p>
          </div>
        </div>

        {/* 프로그레스 바 */}
        <div className="space-y-1">
          <input
            type="range"
            min={0}
            max={duration || 100}
            value={currentTime}
            onChange={(e) => {
              const val = Number(e.target.value);
              setCurrentTime(val);
              if (audioRef.current) audioRef.current.currentTime = val;
            }}
            className="w-full h-1.5 bg-slate-800 rounded-lg appearance-none cursor-pointer accent-slate-100 transition-all"
          />
          <div className="flex justify-between text-[10px] text-slate-500 font-medium">
            <span>{Math.floor(currentTime / 60)}:{('0' + Math.floor(currentTime % 60)).slice(-2)}</span>
            <span>{Math.floor(duration / 60)}:{('0' + Math.floor(duration % 60)).slice(-2)}</span>
          </div>
        </div>

        {/* 재생 제어 버튼 묶음 (정지/재생, 이전 곡, 다음 곡) */}
        <div className="flex items-center justify-center space-x-8 pt-1">
          <button 
            onClick={handlePrev}
            className="text-slate-400 hover:text-white transition-transform active:scale-95 p-2"
          >
            <svg className="w-6 h-6 fill-current" viewBox="0 0 24 24">
              <path d="M6 6h2v12H6zm3.5 6l8.5 6V6z"/>
            </svg>
          </button>

          <button
            onClick={togglePlay}
            className="w-14 h-14 rounded-full bg-slate-100 text-slate-950 flex items-center justify-center shadow-xl hover:bg-white transition-transform active:scale-90"
          >
            {isPlaying ? (
              <svg className="w-6 h-6 fill-current" viewBox="0 0 24 24">
                <path d="M6 19h4V5H6v14zm8-14v14h4V5h-4z"/>
              </svg>
            ) : (
              <svg className="w-6 h-6 fill-current ml-0.5" viewBox="0 0 24 24">
                <path d="M8 5v14l11-7z"/>
              </svg>
            )}
          </button>

          <button 
            onClick={handleNext}
            className="text-slate-400 hover:text-white transition-transform active:scale-95 p-2"
          >
            <svg className="w-6 h-6 fill-current" viewBox="0 0 24 24">
              <path d="M6 18l8.5-6L6 6v12zM16 6v12h2V6h-2z"/>
            </svg>
          </button>
        </div>
      </footer>

      {/* 숨겨진 오디오 태그 */}
      <audio ref={audioRef} src={song.audio_url} preload="metadata" />
    </div>
  );
}