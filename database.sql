create table if not exists public.pvp_members (
    guild_id text not null,
    user_id text not null,
    expires_at bigint not null default 0,
    primary key (guild_id, user_id)
);

create table if not exists public.pvp_panels (
    message_id text primary key,
    channel_id text not null,
    guild_id text not null
);

-- Usar únicamente la clave de servidor (service_role) en FadeHost.
-- Nunca subir esa clave a GitHub ni mostrarla a usuarios.
alter table public.pvp_members enable row level security;
alter table public.pvp_panels enable row level security;
