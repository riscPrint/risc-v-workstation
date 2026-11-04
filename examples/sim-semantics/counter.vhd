library ieee;
use ieee.std_logic_1164.all;
use ieee.numeric_std.all;
entity counter is
  port(clk, reset: in std_logic; q: out std_logic_vector(3 downto 0));
end;
architecture rtl of counter is
  signal value: unsigned(3 downto 0);
begin
  process(clk) begin
    if rising_edge(clk) then
      if reset = '1' then value <= (others => '0');
      else value <= value + 1;
      end if;
    end if;
  end process;
  q <= std_logic_vector(value);
end;
