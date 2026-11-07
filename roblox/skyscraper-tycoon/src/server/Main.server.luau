-- Главный серверный скрипт «Небоскрёб Тайкун».
-- Отвечает за деньги, постройку этажей, ветер, улучшения, перерождения и сохранение.
-- Клиент только присылает просьбы ("построй этаж"), а сервер всё проверяет сам.

local Players = game:GetService("Players")
local ReplicatedStorage = game:GetService("ReplicatedStorage")
local MarketplaceService = game:GetService("MarketplaceService")

local Shared = ReplicatedStorage:WaitForChild("Shared")
local Config = require(Shared:WaitForChild("Config"))
local Format = require(Shared:WaitForChild("Format"))
local DataService = require(script.Parent:WaitForChild("DataService"))
local TowerBuilder = require(script.Parent:WaitForChild("TowerBuilder"))

---------------------------------------------------------------------
-- Remotes: каналы связи между клиентом и сервером
---------------------------------------------------------------------
local remotesFolder = ReplicatedStorage:FindFirstChild("Remotes")
if remotesFolder then
	remotesFolder:Destroy()
end
remotesFolder = Instance.new("Folder")
remotesFolder.Name = "Remotes"

local function newRemote(name: string): RemoteEvent
	local remote = Instance.new("RemoteEvent")
	remote.Name = name
	remote.Parent = remotesFolder
	return remote
end

local BuildFloor = newRemote("BuildFloor")
local Collect = newRemote("Collect")
local BuyUpgrade = newRemote("BuyUpgrade")
local Repair = newRemote("Repair")
local Rebirth = newRemote("Rebirth")
local RequestState = newRemote("RequestState")
local StateUpdate = newRemote("StateUpdate")
local Notify = newRemote("Notify")
remotesFolder.Parent = ReplicatedStorage

---------------------------------------------------------------------
-- Сессии игроков (то, что не сохраняется)
---------------------------------------------------------------------
type Session = {
	Plot: TowerBuilder.Plot,
	LastAction: number,
	LastPadCollect: number,
	DoubleIncome: boolean,
	FloorsStat: IntValue,
	RebirthsStat: IntValue,
}

local sessions: { [Player]: Session } = {}

local function notify(player: Player, text: string, kind: string?)
	Notify:FireClient(player, text, kind or "info")
end

local function damagedSet(data: DataService.PlayerData): { [number]: boolean }
	local set = {}
	for _, index in data.Damaged do
		set[index] = true
	end
	return set
end

local function getMultiplier(session: Session, data: DataService.PlayerData): number
	return Config.HeightBonus(#data.Floors)
		* (1 + data.Rebirths * Config.REBIRTH_BONUS)
		* (1 + data.Ads * Config.ADS_BONUS)
		* (if session.DoubleIncome then 2 else 1)
end

local function getIncome(session: Session, data: DataService.PlayerData): number
	local damaged = damagedSet(data)
	local base = 0
	for index, typeId in data.Floors do
		if not damaged[index] then
			local floorType = Config.GetFloorType(typeId)
			if floorType then
				base += floorType.Income
			end
		end
	end
	return base * getMultiplier(session, data)
end

local function getRepairCost(data: DataService.PlayerData): number
	local total = 0
	for _, index in data.Damaged do
		local floorType = Config.GetFloorType(data.Floors[index])
		if floorType then
			total += Config.FloorCost(floorType, index - 1) * Config.REPAIR_COST_PART
		end
	end
	return math.floor(total)
end

local function upgradeLevel(data: DataService.PlayerData, name: string): number
	if name == "Manager" then
		return if data.Manager then 1 else 0
	end
	return (data :: any)[name]
end

local function sendState(player: Player)
	local session = sessions[player]
	local data = DataService.Get(player)
	if not session or not data then
		return
	end

	local floorCosts = {}
	for i, floorType in Config.FloorTypes do
		floorCosts[i] = Config.FloorCost(floorType, #data.Floors)
	end

	local upgrades = {}
	for name, upgrade in Config.Upgrades do
		local level = upgradeLevel(data, name)
		upgrades[name] = {
			Level = level,
			MaxLevel = upgrade.MaxLevel,
			Cost = Config.UpgradeCost(name, level),
		}
	end

	StateUpdate:FireClient(player, {
		Cash = data.Cash,
		Stored = data.Stored,
		Income = getIncome(session, data),
		Multiplier = getMultiplier(session, data),
		Floors = #data.Floors,
		Rebirths = data.Rebirths,
		Manager = data.Manager,
		SafeHeight = Config.SafeHeight(data.Stability),
		DamagedCount = #data.Damaged,
		RepairCost = getRepairCost(data),
		RebirthRequirement = Config.RebirthRequirement(data.Rebirths),
		FloorCosts = floorCosts,
		Upgrades = upgrades,
		DoubleIncome = session.DoubleIncome,
	})
end

---------------------------------------------------------------------
-- Проверка загруженных данных (на случай старых или битых сохранений)
---------------------------------------------------------------------
local function isGoodNumber(value: any): boolean
	return type(value) == "number" and value == value and value >= 0 and value < math.huge
end

local function sanitize(data: DataService.PlayerData)
	if not isGoodNumber(data.Cash) then
		data.Cash = Config.START_CASH
	end
	if not isGoodNumber(data.Stored) then
		data.Stored = 0
	end
	data.Rebirths = if isGoodNumber(data.Rebirths) then math.floor(data.Rebirths) else 0
	data.Stability = math.clamp(
		if isGoodNumber(data.Stability) then math.floor(data.Stability) else 0,
		0,
		Config.Upgrades.Stability.MaxLevel
	)
	data.Ads = math.clamp(if isGoodNumber(data.Ads) then math.floor(data.Ads) else 0, 0, Config.Upgrades.Ads.MaxLevel)

	local floors = {}
	for _, typeId in data.Floors do
		if #floors >= Config.MAX_FLOORS then
			break
		end
		if Config.GetFloorType(typeId) then
			table.insert(floors, typeId)
		end
	end
	data.Floors = floors

	local seen = {}
	local damaged = {}
	for _, index in data.Damaged do
		if type(index) == "number" and floors[index] and not seen[index] then
			seen[index] = true
			table.insert(damaged, index)
		end
	end
	data.Damaged = damaged
end

---------------------------------------------------------------------
-- Вход и выход игроков
---------------------------------------------------------------------
local function moveToPlot(player: Player, character: Model)
	local session = sessions[player]
	if not session then
		return
	end
	character:WaitForChild("HumanoidRootPart", 10)
	task.wait() -- даём персонажу появиться, потом переносим
	if character.Parent then
		character:PivotTo(TowerBuilder.GetSpawnCFrame(session.Plot))
	end
end

local function checkGamePass(player: Player): boolean
	if Config.GAMEPASS_DOUBLE_INCOME == 0 then
		return false
	end
	local ok, owns = pcall(function()
		return MarketplaceService:UserOwnsGamePassAsync(player.UserId, Config.GAMEPASS_DOUBLE_INCOME)
	end)
	return ok and owns == true
end

local function onPlayerAdded(player: Player)
	local data = DataService.Load(player)
	if not player.Parent then
		-- игрок вышел, пока грузились данные
		DataService.Release(player)
		return
	end
	sanitize(data)

	local plot = TowerBuilder.ClaimPlot(player)
	if not plot then
		DataService.Release(player)
		player:Kick("Все участки заняты, зайди на другой сервер 🙏")
		return
	end

	local leaderstats = Instance.new("Folder")
	leaderstats.Name = "leaderstats"
	local floorsStat = Instance.new("IntValue")
	floorsStat.Name = "Этажи"
	floorsStat.Value = #data.Floors
	floorsStat.Parent = leaderstats
	local rebirthsStat = Instance.new("IntValue")
	rebirthsStat.Name = "Реконструкции"
	rebirthsStat.Value = data.Rebirths
	rebirthsStat.Parent = leaderstats
	leaderstats.Parent = player

	local session: Session = {
		Plot = plot,
		LastAction = 0,
		LastPadCollect = 0,
		DoubleIncome = checkGamePass(player),
		FloorsStat = floorsStat,
		RebirthsStat = rebirthsStat,
	}
	sessions[player] = session

	TowerBuilder.Rebuild(plot, data.Floors, data.Damaged)

	-- можно отдалять камеру, чтобы видеть верх башни
	player.CameraMaxZoomDistance = 1500

	player.CharacterAdded:Connect(function(character)
		moveToPlot(player, character)
	end)
	if player.Character then
		task.spawn(moveToPlot, player, player.Character)
	end

	-- офлайн-доход
	local secondsAway = math.clamp(os.time() - data.LastOnline, 0, Config.OFFLINE_MAX_SECONDS)
	local offline = math.floor(getIncome(session, data) * secondsAway * Config.OFFLINE_INCOME_PART)
	data.LastOnline = os.time()

	sendState(player)

	task.delay(3, function()
		if not sessions[player] then
			return
		end
		if offline >= 1 then
			data.Stored += offline
			notify(player, `💤 Пока тебя не было, башня заработала {Format.Number(offline)}! Забери в кассе`, "good")
			sendState(player)
		elseif #data.Floors == 0 then
			notify(player, "👷 Построй первый этаж кнопкой внизу!", "info")
		end
	end)
end

local function onPlayerRemoving(player: Player)
	sessions[player] = nil
	TowerBuilder.ReleasePlot(player)
	DataService.Release(player)
end

---------------------------------------------------------------------
-- Действия игрока
---------------------------------------------------------------------

-- Защита от спама кнопками
local function canAct(session: Session): boolean
	local now = os.clock()
	if now - session.LastAction < 0.12 then
		return false
	end
	session.LastAction = now
	return true
end

local function collect(player: Player)
	local data = DataService.Get(player)
	if not data then
		return
	end
	local amount = math.floor(data.Stored)
	if amount <= 0 then
		return
	end
	data.Stored -= amount
	data.Cash += amount
	notify(player, `💰 +{Format.Number(amount)}`, "money")
	sendState(player)
end

BuildFloor.OnServerEvent:Connect(function(player, typeId)
	local session = sessions[player]
	local data = DataService.Get(player)
	if not session or not data or type(typeId) ~= "number" then
		return
	end
	if not canAct(session) then
		return
	end

	local floorType = Config.GetFloorType(typeId)
	if not floorType then
		return
	end
	local count = #data.Floors
	if count >= Config.MAX_FLOORS then
		notify(player, "🏁 Это максимальная высота! Время для реконструкции", "bad")
		return
	end
	if count < floorType.UnlockFloors then
		notify(player, `🔒 {floorType.Name} откроется с {floorType.UnlockFloors} этажа`, "bad")
		return
	end
	local cost = Config.FloorCost(floorType, count)
	if data.Cash < cost then
		notify(player, `Не хватает {Format.Number(cost - data.Cash)} 💰`, "bad")
		return
	end

	data.Cash -= cost
	table.insert(data.Floors, floorType.Id)
	data.TotalFloorsBuilt += 1
	TowerBuilder.AddFloor(session.Plot, floorType.Id, false)

	local newCount = #data.Floors
	session.FloorsStat.Value = newCount

	if newCount % Config.HEIGHT_BONUS_EVERY == 0 then
		local bonus = string.format("%.1f", Config.HeightBonus(newCount))
		notify(player, `🎉 {newCount} этажей! Бонус высоты: x{bonus}`, "good")
	end
	for _, other in Config.FloorTypes do
		if other.UnlockFloors == newCount and newCount > 0 then
			notify(player, `🔓 Открыт новый этаж: {other.Emoji} {other.Name}!`, "good")
		end
	end
	if newCount == Config.SafeHeight(data.Stability) + 1 then
		notify(player, "🌪️ Башня выше безопасной высоты! Ветер может повредить верхние этажи", "bad")
	end
	if newCount == Config.RebirthRequirement(data.Rebirths) then
		notify(player, "♻️ Доступна реконструкция! Она даст постоянный бонус к доходу", "good")
	end

	sendState(player)
end)

Collect.OnServerEvent:Connect(function(player)
	local session = sessions[player]
	if session and canAct(session) then
		collect(player)
	end
end)

BuyUpgrade.OnServerEvent:Connect(function(player, name)
	local session = sessions[player]
	local data = DataService.Get(player)
	if not session or not data or type(name) ~= "string" then
		return
	end
	local upgrade = Config.Upgrades[name]
	if not upgrade or not canAct(session) then
		return
	end

	local level = upgradeLevel(data, name)
	if level >= upgrade.MaxLevel then
		notify(player, "Уже максимальный уровень ⭐", "bad")
		return
	end
	local cost = Config.UpgradeCost(name, level)
	if data.Cash < cost then
		notify(player, `Не хватает {Format.Number(cost - data.Cash)} 💰`, "bad")
		return
	end

	data.Cash -= cost
	if name == "Manager" then
		data.Manager = true
		-- менеджер сразу забирает то, что лежит в кассе
		data.Cash += data.Stored
		data.Stored = 0
		notify(player, "🧑‍💼 Менеджер нанят! Теперь деньги идут сразу на счёт", "good")
	elseif name == "Stability" then
		data.Stability += 1
		notify(player, `🏗️ Безопасная высота: {Config.SafeHeight(data.Stability)} этажей`, "good")
	elseif name == "Ads" then
		data.Ads += 1
		notify(player, `📢 Реклама ур. {data.Ads}: +{math.floor(data.Ads * Config.ADS_BONUS * 100 + 0.5)}% к доходу`, "good")
	end
	sendState(player)
end)

Repair.OnServerEvent:Connect(function(player)
	local session = sessions[player]
	local data = DataService.Get(player)
	if not session or not data or not canAct(session) then
		return
	end
	if #data.Damaged == 0 then
		return
	end
	local cost = getRepairCost(data)
	if data.Cash < cost then
		notify(player, `Ремонт стоит {Format.Number(cost)} 💰`, "bad")
		return
	end

	data.Cash -= cost
	for _, index in data.Damaged do
		TowerBuilder.SetDamaged(session.Plot, index, data.Floors[index], false)
	end
	notify(player, `🔧 Починено этажей: {#data.Damaged}`, "good")
	data.Damaged = {}
	sendState(player)
end)

Rebirth.OnServerEvent:Connect(function(player)
	local session = sessions[player]
	local data = DataService.Get(player)
	if not session or not data or not canAct(session) then
		return
	end
	local need = Config.RebirthRequirement(data.Rebirths)
	if #data.Floors < need then
		notify(player, `Нужно {need} этажей для реконструкции`, "bad")
		return
	end

	data.Rebirths += 1
	data.Cash = Config.START_CASH
	data.Stored = 0
	data.Floors = {}
	data.Damaged = {}
	data.Stability = 0
	data.Ads = 0
	-- менеджер остаётся навсегда

	TowerBuilder.ClearTower(session.Plot)
	session.FloorsStat.Value = 0
	session.RebirthsStat.Value = data.Rebirths

	notify(
		player,
		`♻️ Реконструкция #{data.Rebirths}! Доход навсегда x{string.format("%.1f", 1 + data.Rebirths * Config.REBIRTH_BONUS)}`,
		"good"
	)
	sendState(player)
	task.spawn(DataService.Save, player)
end)

RequestState.OnServerEvent:Connect(function(player)
	sendState(player)
end)

MarketplaceService.PromptGamePassPurchaseFinished:Connect(function(player, passId, purchased)
	if purchased and passId == Config.GAMEPASS_DOUBLE_INCOME and sessions[player] then
		sessions[player].DoubleIncome = true
		notify(player, "⚡ x2 к доходу навсегда! Спасибо за поддержку", "good")
		sendState(player)
	end
end)

---------------------------------------------------------------------
-- Запуск
---------------------------------------------------------------------
local plots = TowerBuilder.CreatePlots()

-- Зелёная площадка собирает кассу, если на неё встал владелец участка
for _, plot in plots do
	plot.Pad.Touched:Connect(function(hit)
		local character = hit.Parent
		local player = character and Players:GetPlayerFromCharacter(character)
		if not player or player ~= plot.Owner then
			return
		end
		local session = sessions[player]
		if not session or os.clock() - session.LastPadCollect < 1 then
			return
		end
		session.LastPadCollect = os.clock()
		collect(player)
	end)
end

Players.PlayerAdded:Connect(onPlayerAdded)
Players.PlayerRemoving:Connect(onPlayerRemoving)
for _, player in Players:GetPlayers() do
	task.spawn(onPlayerAdded, player)
end

-- Доход каждую секунду
task.spawn(function()
	while true do
		local dt = task.wait(1)
		for player, session in sessions do
			local data = DataService.Get(player)
			if data then
				local earned = getIncome(session, data) * dt
				if data.Manager then
					data.Cash += earned
				else
					data.Stored += earned
				end
				sendState(player)
			end
		end
	end
end)

-- Шторм
task.spawn(function()
	while true do
		task.wait(math.random(Config.WIND_MIN, Config.WIND_MAX))
		Notify:FireAllClients(
			`🌪️ Шторм через {Config.WIND_WARNING} секунд! Высокие этажи могут пострадать`,
			"wind_warning"
		)
		task.wait(Config.WIND_WARNING)

		for player, session in sessions do
			local data = DataService.Get(player)
			if not data then
				continue
			end
			local safe = Config.SafeHeight(data.Stability)
			local damaged = damagedSet(data)
			local hits = 0
			for index = safe + 1, #data.Floors do
				if not damaged[index] and math.random() < Config.WIND_DAMAGE_CHANCE then
					table.insert(data.Damaged, index)
					TowerBuilder.SetDamaged(session.Plot, index, data.Floors[index], true)
					hits += 1
				end
			end

			if hits > 0 then
				notify(player, `🌪️ Ветер повредил {hits} эт.! Они не приносят доход, пока не починишь`, "wind")
			else
				notify(player, "🌪️ Шторм прошёл, твоя башня цела!", "wind")
			end
			sendState(player)
		end
	end
end)

-- Автосохранение
task.spawn(function()
	while true do
		task.wait(Config.AUTOSAVE_INTERVAL)
		for player in sessions do
			task.spawn(DataService.Save, player)
		end
	end
end)

game:BindToClose(function()
	DataService.SaveAll()
end)

print("[Небоскрёб Тайкун] Сервер запущен ✅")
