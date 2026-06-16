// SPDX-FileCopyrightText: Copyright (c) 2024–2026, NVIDIA CORPORATION & AFFILIATES. All rights reserved.
// SPDX-License-Identifier: BSD-2-Clause

import { Mic, MicOff } from "lucide-react";
import { useState } from "react";

interface Props {
  stream: MediaStream;
}
export default function MicrophoneButton(props: Props) {
  const [isMuted, setIsMuted] = useState(false);

  function onClick() {
    if (isMuted) {
      // If currently muted, unmute by enabling tracks
      props.stream.getAudioTracks().forEach((track) => (track.enabled = true));
    } else {
      // If currently not muted, mute by disabling tracks
      props.stream.getAudioTracks().forEach((track) => (track.enabled = false));
    }
    setIsMuted(!isMuted);
  }
  return (
    <button
      onClick={onClick}
      className="bg-nvidia px-4 py-2 ml-2 rounded-lg text-white"
      title={
        isMuted
          ? "Microphone is muted. Click to unmute"
          : "Microphone is active. Click to mute"
      }
    >
      {isMuted ? <MicOff className="w-4" /> : <Mic className="w-4" />}
    </button>
  );
}
