-- Загрузка и сохранение прогресса игроков через DataStore.
-- В Studio сохранения работают, только если включить:
-- Game Settings -> Security -> Enable Studio Access to API Services.

local DataStoreService = game:GetService("DataStoreService")
local ReplicatedStorage = game:GetService("ReplicatedStorage")

local Config = require(ReplicatedStorage:WaitForChild("Shared"):WaitForChild("Config"))

export type PlayerData = {
	Cash: number,
	Stored: number, -- деньги в кассе, ждут сбора
	Floors: { number }, -- типы этажей снизу вверх
	Damaged: { number }, -- номера повреждённых этажей
	Rebirths: number,
	Stability: number,
	Ads: number,
	Manager: boolean,
	LastOnline: number,
	TotalFloorsBuilt: number,
}

type Profile = {
	Data: PlayerData,
	CanSave: boolean, -- false, если загрузка не удалась: тогда не затираем старое сохранение
}

local DataService = {}

local store: DataStore? = nil
do
	local ok, result = pcall(function()
		return DataStoreService:GetDataStore(Config.DATASTORE_NAME)
	end)
	if ok then
		store = result
	else
		warn("[DataService] DataStore недоступен, прогресс не будет сохраняться:", result)
	end
end

local profiles: { [Player]: Profile } = {}

local function defaultData(): PlayerData
	return {
		Cash = Config.START_CASH,
		Stored = 0,
		Floors = {},
		Damaged = {},
		Rebirths = 0,
		Stability = 0,
		Ads = 0,
		Manager = false,
		LastOnline = os.time(),
		TotalFloorsBuilt = 0,
	}
end

-- Добавляет недостающие поля (если в новой версии игры появились новые)
local function reconcile(data: any): PlayerData
	local result = defaultData()
	if type(data) ~= "table" then
		return result
	end
	for key, value in pairs(result) do
		if data[key] ~= nil and type(data[key]) == type(value) then
			(result :: any)[key] = data[key]
		end
	end
	return result
end

local function keyFor(player: Player): string
	return "player_" .. player.UserId
end

function DataService.Load(player: Player): PlayerData
	local loaded = nil
	local success = store == nil -- без DataStore просто играем с нуля

	if store then
		for attempt = 1, 3 do
			local ok, result = pcall(function()
				return (store :: DataStore):GetAsync(keyFor(player))
			end)
			if ok then
				loaded = result
				success = true
				break
			end
			warn(`[DataService] Не удалось загрузить {player.Name} (попытка {attempt}):`, result)
			task.wait(attempt)
		end
	end

	local data = reconcile(loaded)
	profiles[player] = {
		Data = data,
		CanSave = success and store ~= nil,
	}
	return data
end

function DataService.Get(player: Player): PlayerData?
	local profile = profiles[player]
	return if profile then profile.Data else nil
end

function DataService.Save(player: Player): boolean
	local profile = profiles[player]
	if not profile or not profile.CanSave or not store then
		return false
	end
	profile.Data.LastOnline = os.time()

	for attempt = 1, 3 do
		local ok, err = pcall(function()
			(store :: DataStore):UpdateAsync(keyFor(player), function()
				return profile.Data
			end)
		end)
		if ok then
			return true
		end
		warn(`[DataService] Не удалось сохранить {player.Name} (попытка {attempt}):`, err)
		task.wait(attempt)
	end
	return false
end

function DataService.Release(player: Player)
	DataService.Save(player)
	profiles[player] = nil
end

-- Сохраняет всех сразу и ждёт окончания (нужно при выключении сервера)
function DataService.SaveAll()
	local pending = 0
	for player in pairs(profiles) do
		pending += 1
		task.spawn(function()
			DataService.Save(player)
			pending -= 1
		end)
	end
	local started = os.clock()
	while pending > 0 and os.clock() - started < 25 do
		task.wait(0.1)
	end
end

return DataService
