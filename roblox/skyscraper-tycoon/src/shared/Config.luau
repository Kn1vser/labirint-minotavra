-- Все настройки игры в одном месте. Меняй цифры здесь, чтобы настроить баланс.

local Config = {}

-- Стартовые значения
Config.START_CASH = 25
Config.MAX_FLOORS = 300

-- Участки игроков
Config.PLOT_COUNT = 6
Config.PLOT_SPACING = 90 -- расстояние между участками (в студах)
Config.PLOT_SIZE = 44

-- Размер этажа
Config.FLOOR_HEIGHT = 6
Config.FLOOR_WIDTH = 20

-- Каждый следующий этаж дороже предыдущего в FLOOR_COST_GROWTH раз
Config.FLOOR_COST_GROWTH = 1.05

-- Бонус за высоту: +HEIGHT_BONUS_STEP к доходу за каждые HEIGHT_BONUS_EVERY этажей
Config.HEIGHT_BONUS_EVERY = 10
Config.HEIGHT_BONUS_STEP = 0.1

export type FloorType = {
	Id: number,
	Name: string,
	Emoji: string,
	Income: number, -- монет в секунду
	BaseCost: number,
	UnlockFloors: number, -- сколько этажей нужно, чтобы открыть
	Color: Color3,
	WindowColor: Color3,
}

Config.FloorTypes = {
	{
		Id = 1,
		Name = "Квартиры",
		Emoji = "🏠",
		Income = 1,
		BaseCost = 10,
		UnlockFloors = 0,
		Color = Color3.fromRGB(232, 222, 200),
		WindowColor = Color3.fromRGB(140, 190, 230),
	},
	{
		Id = 2,
		Name = "Офис",
		Emoji = "💼",
		Income = 8,
		BaseCost = 120,
		UnlockFloors = 5,
		Color = Color3.fromRGB(120, 130, 145),
		WindowColor = Color3.fromRGB(90, 170, 255),
	},
	{
		Id = 3,
		Name = "Ресторан",
		Emoji = "🍔",
		Income = 50,
		BaseCost = 1500,
		UnlockFloors = 15,
		Color = Color3.fromRGB(196, 92, 60),
		WindowColor = Color3.fromRGB(255, 210, 120),
	},
	{
		Id = 4,
		Name = "Отель",
		Emoji = "🏨",
		Income = 300,
		BaseCost = 20000,
		UnlockFloors = 30,
		Color = Color3.fromRGB(60, 80, 140),
		WindowColor = Color3.fromRGB(255, 240, 180),
	},
	{
		Id = 5,
		Name = "Казино",
		Emoji = "🎰",
		Income = 2000,
		BaseCost = 250000,
		UnlockFloors = 50,
		Color = Color3.fromRGB(110, 30, 120),
		WindowColor = Color3.fromRGB(255, 80, 200),
	},
	{
		Id = 6,
		Name = "Пентхаус",
		Emoji = "👑",
		Income = 15000,
		BaseCost = 3000000,
		UnlockFloors = 80,
		Color = Color3.fromRGB(30, 30, 35),
		WindowColor = Color3.fromRGB(255, 200, 60),
	},
} :: { FloorType }

-- Ветер: раз в WIND_MIN..WIND_MAX секунд дует шторм.
-- Этажи выше безопасной высоты могут повредиться (перестают приносить доход).
Config.WIND_MIN = 150
Config.WIND_MAX = 240
Config.WIND_WARNING = 10 -- за сколько секунд предупредить
Config.WIND_DAMAGE_CHANCE = 0.5
Config.REPAIR_COST_PART = 0.25 -- ремонт этажа = 25% от его цены

-- Улучшения
Config.Upgrades = {
	Stability = {
		Name = "Стабильность",
		Emoji = "🏗️",
		Description = "+10 этажей, которые не боятся ветра",
		BaseCost = 200,
		Growth = 2.2,
		MaxLevel = 30,
	},
	Ads = {
		Name = "Реклама",
		Emoji = "📢",
		Description = "+10% к доходу",
		BaseCost = 500,
		Growth = 1.9,
		MaxLevel = 25,
	},
	Manager = {
		Name = "Менеджер",
		Emoji = "🧑‍💼",
		Description = "Сам собирает кассу",
		BaseCost = 5000,
		Growth = 1,
		MaxLevel = 1,
	},
}
Config.ADS_BONUS = 0.1 -- +10% дохода за уровень рекламы
Config.SAFE_HEIGHT_BASE = 15
Config.SAFE_HEIGHT_PER_LEVEL = 10

-- Реконструкция (перерождение)
Config.REBIRTH_BASE_FLOORS = 40
Config.REBIRTH_FLOORS_PER_REBIRTH = 20
Config.REBIRTH_BONUS = 0.5 -- +50% дохода за каждую реконструкцию

-- Офлайн-доход: доля дохода за время отсутствия
Config.OFFLINE_INCOME_PART = 0.25
Config.OFFLINE_MAX_SECONDS = 8 * 60 * 60

-- Геймпасс x2 дохода. Создай геймпасс в Creator Hub и вставь сюда его ID.
-- 0 = выключено.
Config.GAMEPASS_DOUBLE_INCOME = 0

-- Сохранения
Config.DATASTORE_NAME = "SkyscraperTycoon_v1"
Config.AUTOSAVE_INTERVAL = 60

-- Вспомогательные функции, общие для сервера и клиента

function Config.GetFloorType(id: number): FloorType?
	for _, floorType in Config.FloorTypes do
		if floorType.Id == id then
			return floorType
		end
	end
	return nil
end

-- Цена этажа, который станет номером (floorCount + 1)
function Config.FloorCost(floorType: FloorType, floorCount: number): number
	return math.floor(floorType.BaseCost * Config.FLOOR_COST_GROWTH ^ floorCount)
end

function Config.UpgradeCost(upgradeName: string, level: number): number
	local upgrade = Config.Upgrades[upgradeName]
	return math.floor(upgrade.BaseCost * upgrade.Growth ^ level)
end

function Config.SafeHeight(stabilityLevel: number): number
	return Config.SAFE_HEIGHT_BASE + stabilityLevel * Config.SAFE_HEIGHT_PER_LEVEL
end

function Config.HeightBonus(floorCount: number): number
	return 1 + math.floor(floorCount / Config.HEIGHT_BONUS_EVERY) * Config.HEIGHT_BONUS_STEP
end

function Config.RebirthRequirement(rebirths: number): number
	return Config.REBIRTH_BASE_FLOORS + rebirths * Config.REBIRTH_FLOORS_PER_REBIRTH
end

return Config
