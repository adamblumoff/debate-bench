export type Winner = "pro" | "con" | "tie" | null;

export interface Scores {
  [dimension: string]: number;
}

export interface JudgeScore {
  scores: Scores;
}

export interface JudgeDecision {
  judge_id: string;
  winner: Winner;
  pro: JudgeScore;
  con: JudgeScore;
}

export interface Topic {
  id: string;
  motion?: string;
  category?: string;
}

export interface Turn {
  speaker: "pro" | "con";
  stage?: string;
  content?: string;
  duration_ms?: number | null;
  prompt_tokens?: number | null;
  completion_tokens?: number | null;
}

export interface Transcript {
  debate_id: string;
  benchmark_version?: string;
  rubric_version?: string;
  topic: Topic;
  pro_model_id: string;
  con_model_id: string;
  turns: Turn[];
  seed?: number;
}

export interface DebateAggregate {
  winner: Winner;
  mean_pro: Scores;
  mean_con: Scores;
}

export interface DebateRecord {
  transcript: Transcript;
  aggregate: DebateAggregate;
  judges: JudgeDecision[];
  created_at?: string;
}

export interface ModelStats {
  model_id: string;
  wins: number;
  losses: number;
  ties: number;
  games: number;
  win_rate: number;
  pro_games: number;
  con_games: number;
  pro_win_rate: number;
  con_win_rate: number;
}

export interface HeadToHeadCell {
  row: string;
  col: string;
  win_rate: number;
  samples: number;
}

export interface TopicWinrate {
  topic_id: string;
  category?: string;
  model_id: string;
  wins: number;
  losses: number;
  ties: number;
  win_rate: number;
  samples: number;
}

export interface JudgeAgreementRow {
  judge_a: string;
  judge_b: string;
  agreement_rate: number;
  samples: number;
}

export interface DebateRowForBuilder {
  pro_model_id: string;
  con_model_id: string;
  winner: Winner;
  topic_id: string;
  category?: string;
  [key: string]: string | number | Winner | undefined;
}

export interface JudgeRowForBuilder {
  judge_id: string;
  winner: Winner;
  pro_model_id: string;
  con_model_id: string;
  topic_id: string;
  category?: string;
}

export interface DerivedData {
  models: string[];
  dimensions: string[];
  modelStats: ModelStats[];
  headToHead: HeadToHeadCell[];
  topicWinrates: TopicWinrate[];
  judgeAgreement: JudgeAgreementRow[];
  debateRows: DebateRowForBuilder[];
  judgeRows: JudgeRowForBuilder[];
}
