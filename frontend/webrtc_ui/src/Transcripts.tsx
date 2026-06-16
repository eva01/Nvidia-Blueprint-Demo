// SPDX-FileCopyrightText: Copyright (c) 2024–2026, NVIDIA CORPORATION & AFFILIATES. All rights reserved.
// SPDX-License-Identifier: BSD-2-Clause

import { useEffect, useMemo, useRef, useState } from "react";

interface Props {
  dataChannel: RTCDataChannel | null;
  localUserMessages?: LocalUserMessage[];
  onLatestBotText?: (text: string) => void;
}
interface IncomingDataChannelMessage {
  label: string;
  type: string;
  data: string;
}

interface DataChannelMessage {
  actor: string;
  message_id: string;
  text: string;
}


interface AugmentedMessage extends DataChannelMessage {
  timestamp: Date;
}

export interface LocalUserMessage {
  id: string;
  text: string;
  timestamp: Date;
}

export function Transcripts(props: Props) {
  const { dataChannel, localUserMessages = [], onLatestBotText } = props;
  const [transcripts, setTranscripts] = useState<AugmentedMessage[]>([]);
  const bottomRef = useRef<HTMLDivElement>(null);

  // Clear transcripts when a new connection is established
  useEffect(() => {
    if (dataChannel) {
      console.log("New DataChannel connection detected, clearing old transcripts");
      setTranscripts([]);
    }
  }, [dataChannel]);

  useEffect(() => {
    function onDataChannelMessage(event: MessageEvent) {
      try {
        const envelope = JSON.parse(event.data) as IncomingDataChannelMessage | any;
        const payload = typeof (envelope as any)?.data === "string" ? JSON.parse((envelope as any).data) : (envelope as any)?.data;

        // Ignore control/config messages (e.g., { type: "tts_voices" | "tts_voice_current", ... })
        if (payload && typeof payload === "object" && (payload as any).type) {
          return;
        }

        const message = (payload || {}) as Partial<DataChannelMessage>;
        // Only process transcript-like messages that have required fields
        if (
          typeof message.actor !== "string" ||
          typeof message.message_id !== "string" ||
          typeof message.text !== "string"
        ) {
          return;
        }

        // Create a fully typed, non-optional copy for use in closures
        const validMessage: DataChannelMessage = {
          actor: message.actor as string,
          message_id: message.message_id as string,
          text: message.text as string,
        };

        setTranscripts((prev) => {
          const existingMessage = prev.find(
            (t) => t.actor === validMessage.actor && t.message_id === validMessage.message_id
          );
          if (existingMessage) {
            existingMessage.text = validMessage.text;
          } else {
            prev.push({ ...validMessage, timestamp: new Date() });
          }
          return [...prev];
        });
      } catch {
        // Ignore non-JSON or unexpected payloads
      }
    }
    dataChannel?.addEventListener("message", onDataChannelMessage);
    return () => {
      dataChannel?.removeEventListener("message", onDataChannelMessage);
    };
  }, [dataChannel]);

  const filteredTranscripts = useMemo(
    () => transcripts.filter((transcript) => {
      const actor = transcript.actor?.toLowerCase()?.trim();
      const isSystem = actor === "system";
      return !isSystem;
    }),
    [transcripts]
  );

  useEffect(() => {
    const botTranscripts = filteredTranscripts.filter(
      (transcript) => transcript.actor?.toLowerCase()?.trim() === "bot"
    );
    const latestBot = botTranscripts[botTranscripts.length - 1];
    onLatestBotText?.(latestBot?.text ?? "");
  }, [filteredTranscripts, onLatestBotText]);

  const visibleTranscripts: AugmentedMessage[] = useMemo(
    () => [
      ...filteredTranscripts,
      ...localUserMessages.map((message) => ({
        actor: "user",
        message_id: message.id,
        text: message.text,
        timestamp: message.timestamp,
      })),
    ].sort((left, right) => left.timestamp.getTime() - right.timestamp.getTime()),
    [filteredTranscripts, localUserMessages]
  );

  useEffect(() => {
    bottomRef.current?.scrollIntoView({ block: "end" });
  }, [visibleTranscripts]);

  return (
    <>
      {visibleTranscripts.map((transcript) => (
        <div
          className="font-mono text-lg flex items-start mb-2"
          key={transcript.actor + transcript.message_id}
        >
          {transcript.timestamp.toTimeString().slice(0, 8)}
          <div className="flex items-center ml-3 mr-3 min-w-[60px]">
            <div
              className={`rounded-lg text-white text-sm p-1 flex justify-center items-center min-w-full ${transcript.actor === "bot" ? "bg-nvidia" : "bg-cyan-700"
                }`}
            >
              {transcript.actor}
            </div>
          </div>
          <div>:</div>
          <div className="pl-3"> </div>
          <div className="flex-1">{transcript.text}</div>
        </div>
      ))}
      <div ref={bottomRef} />
    </>
  );
}
