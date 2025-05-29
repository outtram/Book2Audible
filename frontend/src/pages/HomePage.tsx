import React from 'react';
import { Link } from 'react-router-dom';

export const HomePage: React.FC = () => {
  return (
    <div className="px-40 flex flex-1 justify-center py-5">
      <div className="layout-content-container flex flex-col max-w-[960px] flex-1">
        <div className="@container">
          <div className="@[480px]:p-4">
            <div
              className="flex min-h-[480px] flex-col gap-6 bg-cover bg-center bg-no-repeat @[480px]:gap-8 @[480px]:rounded-lg items-center justify-center p-4"
              style={{
                backgroundImage: 'linear-gradient(rgba(0, 0, 0, 0.1) 0%, rgba(0, 0, 0, 0.4) 100%), url("https://lh3.googleusercontent.com/aida-public/AB6AXuCKrpC-VGVgfe0sn3fXXUrhuVl49350H35eLcdE8f3JnNXhkPbzgh4_Mqz5JKuwpn0dwmHnwKsJQ7547X6bN-i9PIStqpe40Iy19kFckC3cpW5R1U46cHGlnpEK6wNrgOg1o3xQWGhy6Sn38Vm_r4fwG2lb2eqoApRGJF3-FRMF0oi5E0tfeQH7QDAB64AiMnWBY6X7577Phrvf9RFU-Hmez67Zs4h4fEJtChYUl5RiXVVs9Va5HR8oOyAi2Vda4rSqO4d0JZCuc323")'
              }}
            >
              <div className="flex flex-col gap-2 text-center">
                <h1 className="text-white text-4xl font-black leading-tight tracking-[-0.033em] @[480px]:text-5xl @[480px]:font-black @[480px]:leading-tight @[480px]:tracking-[-0.033em]">
                  Transform Your Books into Captivating Audio Experiences
                </h1>
                <h2 className="text-white text-sm font-normal leading-normal @[480px]:text-base @[480px]:font-normal @[480px]:leading-normal">
                  Orpheus TTS offers a seamless way to convert your written books into high-quality audiobooks. Experience your favorite stories in a new way, perfect for
                  commutes, workouts, or relaxing at home.
                </h2>
              </div>
              <Link
                to="/upload"
                className="flex min-w-[84px] max-w-[480px] cursor-pointer items-center justify-center overflow-hidden rounded-lg h-10 px-4 @[480px]:h-12 @[480px]:px-5 bg-primary-600 text-primary-50 text-sm font-bold leading-normal tracking-[0.015em] @[480px]:text-base @[480px]:font-bold @[480px]:leading-normal @[480px]:tracking-[0.015em]"
              >
                <span className="truncate">Start Converting</span>
              </Link>
            </div>
          </div>
        </div>
      </div>
    </div>
  );
};