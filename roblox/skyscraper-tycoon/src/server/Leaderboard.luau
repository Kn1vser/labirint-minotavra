-- Глобальная таблица рекордов: самые высокие башни на всех серверах.
-- Табло стоит в центре карты. Работает только в опубликованной игре
-- или в Studio с включённым доступом к API Services.

local DataStoreService = game:GetService("DataStoreService")
local Players = game:GetService("Players")
local ReplicatedStorage = game:GetService("ReplicatedStorage")

local Config = require(ReplicatedStorage:WaitForChild("Shared"):WaitForChild("Config"))
local Format = require(ReplicatedStorage:WaitForChild("Shared"):WaitForChild("Format"))

local Leaderboard = {}

local store: OrderedDataStore? = nil
do
	local ok, result = pcall(function()
		return DataStoreService:GetOrderedDataStore(Config.LEADERBOARD_NAME)
	end)
	if ok then
		store = result
	end
end

local rowLabels: { TextLabel } = {}
local nameCache: { [number]: string } = {}

local function getName(userId: number): string
	if nameCache[userId] then
		return nameCache[userId]
	end
	local ok, name = pcall(function()
		return Players:GetNameFromUserIdAsync(userId)
	end)
	local result = if ok and name then name else "???"
	nameCache[userId] = result
	return result
end

-- Строит табло в указанном месте (лицевая сторона смотрит в +Z этого CFrame)
function Leaderboard.CreateBoard(cframe: CFrame)
	local model = Instance.new("Model")
	model.Name = "Leaderboard"

	local board = Instance.new("Part")
	board.Name = "Board"
	board.Anchored = true
	board.Size = Vector3.new(18, 14, 1)
	board.CFrame = cframe
	board.Material = Enum.Material.SmoothPlastic
	board.Color = Color3.fromRGB(24, 27, 40)
	board.Parent = model

	for _, side in { -1, 1 } do
		local post = Instance.new("Part")
		post.Anchored = true
		post.Size = Vector3.new(1, cframe.Position.Y, 1)
		post.CFrame = CFrame.new((cframe * CFrame.new(side * 8, 0, 0)).Position.X, cframe.Position.Y / 2, cframe.Position.Z)
		post.Color = Color3.fromRGB(50, 55, 70)
		post.Parent = model
	end

	local gui = Instance.new("SurfaceGui")
	gui.Face = Enum.NormalId.Back
	gui.SizingMode = Enum.SurfaceGuiSizingMode.PixelsPerStud
	gui.PixelsPerStud = 30
	gui.Parent = board

	local layout = Instance.new("UIListLayout")
	layout.SortOrder = Enum.SortOrder.LayoutOrder
	layout.Padding = UDim.new(0, 4)
	layout.Parent = gui

	local title = Instance.new("TextLabel")
	title.Size = UDim2.fromScale(1, 0.14)
	title.BackgroundTransparency = 1
	title.Font = Enum.Font.GothamBold
	title.TextScaled = true
	title.TextColor3 = Color3.fromRGB(255, 205, 60)
	title.Text = "🏆 Самые высокие башни"
	title.LayoutOrder = 0
	title.Parent = gui

	for i = 1, Config.LEADERBOARD_SIZE do
		local row = Instance.new("TextLabel")
		row.Size = UDim2.fromScale(1, 0.08)
		row.BackgroundTransparency = 1
		row.Font = Enum.Font.GothamBold
		row.TextScaled = true
		row.TextXAlignment = Enum.TextXAlignment.Left
		row.TextColor3 = if i == 1
			then Color3.fromRGB(255, 215, 80)
			elseif i == 2 then Color3.fromRGB(210, 215, 230)
			elseif i == 3 then Color3.fromRGB(220, 150, 90)
			else Color3.new(1, 1, 1)
		row.Text = ""
		row.LayoutOrder = i
		row.Parent = gui

		local pad = Instance.new("UIPadding")
		pad.PaddingLeft = UDim.new(0.05, 0)
		pad.Parent = row
		rowLabels[i] = row
	end

	if not store then
		rowLabels[1].Text = "Таблица заработает после публикации игры"
	end

	model.Parent = workspace
end

-- Записывает рекорд игрока (вызывается при сохранении)
function Leaderboard.Submit(userId: number, bestFloors: number)
	if not store or bestFloors <= 0 then
		return
	end
	pcall(function()
		(store :: OrderedDataStore):SetAsync(tostring(userId), math.floor(bestFloors))
	end)
end

function Leaderboard.Refresh()
	if not store then
		return
	end
	local ok, pages = pcall(function()
		return (store :: OrderedDataStore):GetSortedAsync(false, Config.LEADERBOARD_SIZE)
	end)
	if not ok then
		return
	end
	local entries = pages:GetCurrentPage()
	for i = 1, Config.LEADERBOARD_SIZE do
		local entry = entries[i]
		if entry then
			local name = getName(tonumber(entry.key) or 0)
			rowLabels[i].Text = `{i}. {name} — {Format.Number(entry.value)} эт.`
		else
			rowLabels[i].Text = ""
		end
	end
end

function Leaderboard.Start()
	task.spawn(function()
		while true do
			Leaderboard.Refresh()
			task.wait(Config.LEADERBOARD_REFRESH)
		end
	end)
end

return Leaderboard
