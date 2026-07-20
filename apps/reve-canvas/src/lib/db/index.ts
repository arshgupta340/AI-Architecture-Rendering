import "server-only";

import type { CanvasLayer } from "@/lib/model";
import { createServerSupabase } from "@/lib/supabase/server";
import { hasSupabaseConfig } from "@/lib/supabase/config";

export interface ProjectSummary {
  id: string;
  name: string;
  sourceImagePath: string;
  createdAt: string;
  latestSnapshotId: string | null;
}

export function isPersistenceConfigured(): boolean {
  return hasSupabaseConfig();
}

export async function getUser(): Promise<{ id: string; email: string } | null> {
  const supabase = await createServerSupabase();
  if (!supabase) return null;

  const { data } = await supabase.auth.getUser();
  if (!data.user?.email) return null;
  return { id: data.user.id, email: data.user.email };
}

function dataUrlToFile(dataUrl: string): { bytes: Buffer; contentType: string; extension: string } | null {
  const match = /^data:([^;]+);base64,(.+)$/.exec(dataUrl);
  if (!match) return null;

  const contentType = match[1];
  const extension = ({ "image/jpeg": "jpg", "image/png": "png", "image/webp": "webp" } as Record<string, string>)[contentType];
  if (!extension) return null;
  return { bytes: Buffer.from(match[2], "base64"), contentType, extension };
}

export async function createProject(input: {
  name: string;
  sourceImageDataUrl: string;
  width: number;
  height: number;
}): Promise<{ projectId: string; snapshotId: string } | null> {
  const supabase = await createServerSupabase();
  const user = await getUser();
  const image = dataUrlToFile(input.sourceImageDataUrl);
  if (!supabase || !user || !image) return null;

  const path = `${user.id}/${crypto.randomUUID()}.${image.extension}`;
  const upload = await supabase.storage.from("images").upload(path, image.bytes, {
    contentType: image.contentType,
    upsert: false,
  });
  if (upload.error) return null;

  const project = await supabase.from("projects").insert({
    owner: user.id,
    name: input.name,
    source_image_path: path,
    source_width: input.width,
    source_height: input.height,
  }).select("id").single();
  if (project.error || !project.data) return null;

  const snapshot = await supabase.from("snapshots").insert({
    project_id: project.data.id,
    image_path: path,
    layout: {},
  }).select("id").single();
  if (snapshot.error || !snapshot.data) return null;

  return { projectId: project.data.id, snapshotId: snapshot.data.id };
}

export async function saveLayers(projectId: string, layers: CanvasLayer[]): Promise<void> {
  const supabase = await createServerSupabase();
  if (!supabase) return;

  const rows = layers.map((layer, sortOrder) => ({
    project_id: projectId,
    region_key: layer.id,
    name: layer.name,
    semantic: layer.semantic,
    type: layer.type,
    bbox: layer.bbox,
    prompt: layer.prompt,
    is_building: layer.isBuilding,
    sort_order: sortOrder,
  }));
  if (rows.length === 0) return;
  await supabase.from("layers").upsert(rows, { onConflict: "project_id,region_key" });
}

export async function recordEdit(input: {
  projectId: string;
  layerId: string;
  kind: string;
  materialId: string;
  facet?: string;
  baseSnapshotId: string;
  resultImageDataUrl: string;
  layout: unknown;
  creditsCost: number;
}): Promise<{ editId: string; snapshotId: string } | null> {
  const supabase = await createServerSupabase();
  const user = await getUser();
  const image = dataUrlToFile(input.resultImageDataUrl);
  if (!supabase || !user || !image) return null;

  const edit = await supabase.from("edits").insert({
    project_id: input.projectId,
    layer_id: input.layerId,
    kind: input.kind,
    material_id: input.materialId,
    facet: input.facet ?? null,
    base_snapshot_id: input.baseSnapshotId,
    status: "running",
    credits_cost: input.creditsCost,
  }).select("id").single();
  if (edit.error || !edit.data) return null;

  const path = `${user.id}/${crypto.randomUUID()}.${image.extension}`;
  const upload = await supabase.storage.from("images").upload(path, image.bytes, {
    contentType: image.contentType,
    upsert: false,
  });
  if (upload.error) return null;

  const snapshot = await supabase.from("snapshots").insert({
    project_id: input.projectId,
    image_path: path,
    layout: input.layout,
    parent_id: input.baseSnapshotId,
    produced_by_edit_id: edit.data.id,
  }).select("id").single();
  if (snapshot.error || !snapshot.data) return null;

  const completed = await supabase.from("edits").update({
    result_snapshot_id: snapshot.data.id,
    status: "completed",
  }).eq("id", edit.data.id);
  if (completed.error) return null;

  return { editId: edit.data.id, snapshotId: snapshot.data.id };
}

export async function listProjects(): Promise<ProjectSummary[]> {
  const supabase = await createServerSupabase();
  if (!supabase) return [];

  const { data, error } = await supabase.from("projects").select("id,name,source_image_path,created_at,snapshots(id,created_at)").order("created_at", { ascending: false });
  if (error || !data) return [];
  return data.map((project) => {
    const snapshots = [...(project.snapshots ?? [])].sort((a, b) => b.created_at.localeCompare(a.created_at));
    return {
      id: project.id,
      name: project.name,
      sourceImagePath: project.source_image_path,
      createdAt: project.created_at,
      latestSnapshotId: snapshots[0]?.id ?? null,
    };
  });
}

export async function getCreditBalance(): Promise<number | null> {
  const supabase = await createServerSupabase();
  if (!supabase) return null;

  const { data, error } = await supabase.from("credit_ledger").select("balance_after").order("created_at", { ascending: false }).limit(1).maybeSingle();
  if (error || !data) return null;
  return data.balance_after;
}
